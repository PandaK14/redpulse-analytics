"""Scraper for EuroCup Basketball, backed by Euroleague Basketball's own
public APIs (the same ones euroleaguebasketball.net/eurocup itself is built
on — there's no need to scrape its Next.js-rendered HTML):

  - Schedule + final scores + box score:
    api-live.euroleague.net/v2/competitions/U/seasons/{season}/games[/...] —
    "U" is the EuroCup competition code, {season} looks like "U2025" for the
    2025-26 season. Clean JSON, no auth required.
  - Play-by-play + shot coordinates: the older live.euroleague.net/api/*
    endpoints (PlayByPlay, Points) that euroleague_api and similar community
    tools rely on. Coordinates are in cm with the basket at (0, 0).
"""

import time
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Game, Player, PlayByPlayEvent, PlayerGameStats, ShotEvent
from app.scrapers.common import (
    discard_pbp_if_score_mismatch,
    find_or_create_competition,
    find_or_create_player,
    find_or_create_team,
)

V2_BASE_URL = "https://api-live.euroleague.net/v2/competitions/U/seasons"
LIVE_BASE_URL = "https://live.euroleague.net/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RedPulseAnalytics/1.0; personal fan-built analytics tool)"}

HAPOEL_JERUSALEM_CLUB_CODE = "JER"


class EuroCupScraper:
    def __init__(self, client: Optional[httpx.Client] = None):
        self.client = client or httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)

    def _get(self, url: str, params: Optional[dict] = None, max_retries: int = 4) -> httpx.Response:
        """GET with Cloudflare-rate-limit awareness: api-live.euroleague.net
        returns 429 with a `Retry-After` header (observed ~20s) under
        sustained sequential load, e.g. a full-season backfill."""
        for attempt in range(max_retries + 1):
            resp = self.client.get(url, params=params)
            if resp.status_code != 429:
                return resp
            wait = int(resp.headers.get("retry-after", 20)) + 1
            time.sleep(wait)
        return resp

    def sync(self, db: Session, season_code: str = "U2025", max_games: Optional[int] = None, delay: float = 0.4) -> int:
        games = self.fetch_schedule(season_code)
        games = [g for g in games if g["played"]]
        if max_games is not None:
            games = games[:max_games]

        find_or_create_competition(db, "EUROCUP", "EuroCup", _season_label(season_code))
        db.commit()

        synced = 0
        for g in games:
            game_id = f"EL_{season_code}_{g['gameCode']}"
            if db.get(Game, game_id):
                continue
            try:
                self._sync_one_game(db, g, season_code, game_id)
                db.commit()
                synced += 1
            except (httpx.HTTPError, KeyError, ValueError, AttributeError, IndexError, SQLAlchemyError):
                db.rollback()
            time.sleep(delay)
        return synced

    def fetch_schedule(self, season_code: str) -> list[dict]:
        resp = self._get(f"{V2_BASE_URL}/{season_code}/games")
        resp.raise_for_status()
        games = resp.json()["data"]
        return [
            {
                "gameCode": g["gameCode"],
                "round": g["round"],
                "date": g["date"],
                "played": g["played"],
                "home_code": g["local"]["club"]["code"],
                "home_name": g["local"]["club"]["name"],
                "home_score": g["local"]["score"],
                "away_code": g["road"]["club"]["code"],
                "away_name": g["road"]["club"]["name"],
                "away_score": g["road"]["score"],
            }
            for g in games
        ]

    def _team_id_for(self, code: str) -> str:
        return "HAPOEL_JLM" if code == HAPOEL_JERUSALEM_CLUB_CODE else code

    def _ensure_pbp_player(self, db: Session, team_id: str, player_id: str, raw_name: Optional[str]) -> str:
        """The box score's player list is expected to cover everyone, but the
        two feeds don't always agree — a player referenced in play-by-play
        who isn't already known would otherwise become a nameless foreign
        key. PLAYER is "LAST, FIRST"; fall back to the bare id if absent.

        Returns the id to actually use as the FK on this event: normally
        player_id itself, but find_or_create_player's Hapoel Jerusalem
        dedup can resolve to a *different* existing row (matched by name or
        jersey) — callers must use the returned id, not the raw one, or
        events end up pointing at a player row that was never created.
        """
        if db.get(Player, player_id) is not None:
            return player_id
        if raw_name:
            last, _, first = raw_name.partition(", ")
            name = f"{first.title()} {last.title()}".strip()
        else:
            name = player_id
        return find_or_create_player(db, team_id, player_id, name).id

    def _resolve_starting_five(self, db: Session, box_score: Optional[dict], side: str, team_id: str) -> set:
        """Same resolution concern as _ensure_pbp_player: a starter's raw
        "EL_{code}" id may have been merged into a different existing row
        (e.g. a Hapoel Jerusalem player already created from a Winner League
        game) — must seed the lineup with the resolved id, not the raw one."""
        if not box_score:
            return set()
        resolved = set()
        for entry in box_score[side]["players"]:
            if not entry["stats"].get("startFive"):
                continue
            info = entry["player"]["person"]
            raw_id = f"EL_{info['code']}"
            last, _, first = info["name"].partition(", ")
            name = f"{first.title()} {last.title()}".strip()
            resolved.add(find_or_create_player(db, team_id, raw_id, name).id)
        return resolved

    def _sync_one_game(self, db: Session, g: dict, season_code: str, game_id: str) -> None:
        home_team_id = self._team_id_for(g["home_code"])
        away_team_id = self._team_id_for(g["away_code"])
        home_team = find_or_create_team(db, home_team_id, g["home_name"], g["home_code"], "EUROCUP", home_team_id == "HAPOEL_JLM")
        away_team = find_or_create_team(db, away_team_id, g["away_name"], g["away_code"], "EUROCUP", away_team_id == "HAPOEL_JLM")

        game = Game(
            id=game_id,
            competition_id="EUROCUP",
            season=_season_label(season_code),
            round=f"Round {g['round']}",
            game_date=_parse_iso(g["date"]),
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            home_score=g["home_score"],
            away_score=g["away_score"],
            is_synced=True,
            raw_pbp_available=False,
        )
        db.add(game)
        db.flush()

        box_score = self._fetch_box_score(season_code, g["gameCode"])
        if box_score:
            self._persist_box_score(db, game, home_team.id, box_score["local"]["players"])
            self._persist_box_score(db, game, away_team.id, box_score["road"]["players"])

        try:
            self._sync_play_by_play(
                db, game, home_team.id, away_team.id, g["home_code"], g["away_code"], season_code, g["gameCode"], box_score
            )
            game.raw_pbp_available = True
        except (httpx.HTTPError, KeyError, ValueError, IndexError):
            pass  # box score already saved; PBP is best-effort

    def _fetch_box_score(self, season_code: str, game_code: int) -> Optional[dict]:
        resp = self._get(f"{V2_BASE_URL}/{season_code}/games/{game_code}/stats")
        if resp.status_code != 200:
            return None
        return resp.json()

    def _persist_box_score(self, db: Session, game: Game, team_id: str, players: list[dict]) -> None:
        for entry in players:
            info = entry["player"]["person"]
            stats = entry["stats"]
            last, _, first = info["name"].partition(", ")
            name = f"{first.title()} {last.title()}".strip()
            player = find_or_create_player(
                db, team_id, f"EL_{info['code']}", name,
                jersey=int(entry["player"].get("dorsal") or 0) or None,
                position=entry["player"].get("positionName"),
                height_cm=info.get("height"),
            )
            db.add(
                PlayerGameStats(
                    id=f"{game.id}_STAT_{player.id}",
                    game_id=game.id,
                    player_id=player.id,
                    team_id=team_id,
                    minutes_played=round(stats.get("timePlayed", 0) / 60, 2),
                    points=int(stats.get("points", 0)),
                    fgm=int(stats.get("fieldGoalsMadeTotal", 0)),
                    fga=int(stats.get("fieldGoalsAttemptedTotal", 0)),
                    fg2m=int(stats.get("fieldGoalsMade2", 0)),
                    fg2a=int(stats.get("fieldGoalsAttempted2", 0)),
                    fg3m=int(stats.get("fieldGoalsMade3", 0)),
                    fg3a=int(stats.get("fieldGoalsAttempted3", 0)),
                    ftm=int(stats.get("freeThrowsMade", 0)),
                    fta=int(stats.get("freeThrowsAttempted", 0)),
                    oreb=int(stats.get("offensiveRebounds", 0)),
                    dreb=int(stats.get("defensiveRebounds", 0)),
                    reb=int(stats.get("totalRebounds", 0)),
                    assists=int(stats.get("assistances", 0)),
                    steals=int(stats.get("steals", 0)),
                    turnovers=int(stats.get("turnovers", 0)),
                    blocks=int(stats.get("blocksFavour", 0)),
                    personal_fouls=int(stats.get("foulsCommited", 0)),
                    fouls_drawn=int(stats.get("foulsReceived", 0)),
                    plus_minus=int(stats.get("plusMinus", 0)),
                    valuation=int(stats.get("valuation", 0)),
                )
            )

    def _sync_play_by_play(
        self, db: Session, game: Game, home_team_id: str, away_team_id: str,
        home_code: str, away_code: str, season_code: str, game_code: int,
        box_score: Optional[dict] = None,
    ) -> None:
        pbp_resp = self._get(f"{LIVE_BASE_URL}/PlayByPlay", params={"gamecode": game_code, "seasoncode": season_code})
        pbp_resp.raise_for_status()
        pbp_data = pbp_resp.json()

        points_resp = self._get(f"{LIVE_BASE_URL}/Points", params={"gamecode": game_code, "seasoncode": season_code})
        points_resp.raise_for_status()
        shots_by_key = {}
        for row in points_resp.json().get("Rows", []):
            key = (row["ID_PLAYER"].strip(), row["MINUTE"], row["CONSOLE"].strip())
            shots_by_key.setdefault(key, []).append(row)

        code_to_team_id = {home_code.strip(): home_team_id, away_code.strip(): away_team_id}
        # The feed's IN/OUT events only ever model substitutions — the five
        # players who start the game are never explicitly announced, so the
        # tracked lineup must be seeded from the box score's startFive flag
        # or it stays wrong (missing players) until enough subs happen.
        lineup: dict[str, set] = {
            home_team_id: self._resolve_starting_five(db, box_score, "local", home_team_id),
            away_team_id: self._resolve_starting_five(db, box_score, "road", away_team_id),
        }
        last_made_shot: dict[str, ShotEvent] = {}
        last_made_shot_pbp: dict[str, PlayByPlayEvent] = {}
        pbp_counter = 0
        shot_counter = 0
        # POINTS_A/POINTS_B are only populated by the feed on the scoring
        # play itself (null on every other row) — carry the last known value
        # forward rather than treating a null as a reset to 0.
        running_home_score = 0
        running_away_score = 0

        quarters = [
            pbp_data.get("FirstQuarter", []), pbp_data.get("SecondQuarter", []),
            pbp_data.get("ThirdQuarter", []), pbp_data.get("ForthQuarter", []),
            pbp_data.get("ExtraTime", []) or [],
        ]

        for period, plays in enumerate(quarters, start=1):
            for play in plays:
                team_code = (play.get("CODETEAM") or "").strip()
                team_id = code_to_team_id.get(team_code)
                play_type = play["PLAYTYPE"]

                if play.get("POINTS_A") is not None:
                    running_home_score = play["POINTS_A"]
                if play.get("POINTS_B") is not None:
                    running_away_score = play["POINTS_B"]

                if play_type in ("IN", "OUT") and team_id:
                    player_key = _pbp_player_id(play.get("PLAYER_ID"))
                    if not player_key:
                        continue
                    player_key = self._ensure_pbp_player(db, team_id, player_key, play.get("PLAYER"))
                    if play_type == "IN":
                        lineup[team_id].add(player_key)
                    else:
                        lineup[team_id].discard(player_key)
                    continue

                if play_type not in _EVENT_TYPE_MAP or not team_id:
                    continue

                player_id = _pbp_player_id(play.get("PLAYER_ID"))
                if player_id:
                    player_id = self._ensure_pbp_player(db, team_id, player_id, play.get("PLAYER"))
                home_score = running_home_score
                away_score = running_away_score

                if play_type == "AS" and player_id and team_id in last_made_shot:
                    last_made_shot[team_id].is_assisted = True
                    last_made_shot[team_id].assister_id = player_id
                    last_made_shot_pbp[team_id].secondary_player_id = player_id
                    continue

                pbp_counter += 1
                pbp_event = PlayByPlayEvent(
                    id=f"{game.id}_PBP_{pbp_counter:04d}",
                    game_id=game.id,
                    period=period,
                    game_clock=play.get("MARKERTIME") or "00:00",
                    event_type=_EVENT_TYPE_MAP[play_type],
                    acting_team_id=team_id,
                    primary_player_id=player_id,
                    secondary_player_id=None,
                    home_score=home_score,
                    away_score=away_score,
                    current_lineup_home=list(lineup[home_team_id])[:5],
                    current_lineup_away=list(lineup[away_team_id])[:5],
                )
                db.add(pbp_event)

                if play_type in _SHOT_PLAY_TYPES and player_id:
                    key = ((play.get("PLAYER_ID") or "").strip(), play.get("MINUTE"), (play.get("MARKERTIME") or "").strip())
                    candidates = shots_by_key.get(key, [])
                    shot_row = candidates.pop(0) if candidates else None
                    if shot_row:
                        shot_counter += 1
                        is_made = play_type.endswith("M")
                        shot_event = ShotEvent(
                            id=f"{game.id}_SHOT_{shot_counter:04d}",
                            game_id=game.id,
                            player_id=player_id,
                            team_id=team_id,
                            period=period,
                            game_clock=play.get("MARKERTIME") or "00:00",
                            x_coord=shot_row["COORD_X"],
                            y_coord=shot_row["COORD_Y"],
                            shot_type=_classify_shot_zone(shot_row["COORD_X"], shot_row["COORD_Y"], play_type),
                            is_made=is_made,
                            is_assisted=False,
                            assister_id=None,
                        )
                        db.add(shot_event)
                        if is_made:
                            last_made_shot[team_id] = shot_event
                            last_made_shot_pbp[team_id] = pbp_event

        db.flush()
        discarded = discard_pbp_if_score_mismatch(
            db, game.id, running_home_score, running_away_score, game.home_score, game.away_score
        )
        if discarded:
            raise ValueError(
                f"EuroCup PBP for game {game.id} reconstructs to "
                f"{running_home_score}-{running_away_score}, doesn't match box score "
                f"{game.home_score}-{game.away_score} (a player is likely missing from the live feed for this game)"
            )


_EVENT_TYPE_MAP = {
    "2FGM": "SHOT", "2FGA": "SHOT", "3FGM": "SHOT", "3FGA": "SHOT",
    "FTM": "FREE_THROW", "FTA": "FREE_THROW",
    "D": "REBOUND", "O": "REBOUND",
    "TO": "TURNOVER",
    "CM": "FOUL", "CMU": "FOUL", "CMT": "FOUL", "OF": "FOUL",
    "ST": "STEAL",
    "AS": "ASSIST",
    # Deliberately no "B": it's a bench/coach foul (PLAYER_ID "CO_A"/"CO_B",
    # not a real player), not a block — including it created spurious
    # "player" rows for the bench. Blocks aren't used by any of the
    # possession/rating math, so there's no need to map a real block code.
}
_SHOT_PLAY_TYPES = {"2FGM", "2FGA", "3FGM", "3FGA"}




def _pbp_player_id(raw: Optional[str]) -> Optional[str]:
    """The live PlayByPlay/Points feeds prefix player codes with "P"
    (e.g. "P013906") while the v2 box score endpoint gives the bare code
    ("013906") — normalize to the box score's scheme so ids agree."""
    code = (raw or "").strip()
    if code.upper().startswith("P"):
        code = code[1:]
    return f"EL_{code}" if code else None


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _season_label(season_code: str) -> str:
    year = int(season_code.lstrip("U"))
    return f"{year}-{str(year + 1)[-2:]}"


def _classify_shot_zone(x: float, y: float, play_type: str) -> str:
    dist_m = (x**2 + y**2) ** 0.5 / 100  # euroleague coords are centimeters from the basket
    is_three = play_type.startswith("3")

    if is_three:
        is_corner = abs(x) > 660 and y < 90
        return "Corner-3" if is_corner else "Above-the-Break-3"
    if dist_m < 1.2:
        return "Rim"
    if dist_m < 4.5:
        return "Paint"
    return "Mid-Range"
