"""Scraper for the Israeli Basketball Super League (Winner League) at basket.co.il.

Data sources (reverse-engineered by inspecting the live site — there is no
published API doc):
  - Season schedule + final scores: `results.asp` (server-rendered HTML table).
  - Per-game box score: `game-zone.asp?GameId=X` (server-rendered HTML tables,
    class `stats_tbl`, one per team).
  - Play-by-play + shot coordinates: when a game has live-tracking, its
    game-zone page links to a third-party viewer at
    stats.segevstats.com/realtimestat_heb/index.php?game_id=Y. That page's
    own `get_team_action.php?game_id=Y` endpoint returns the full action log
    (shots with coordX/coordY, substitutions, rebounds, assists, etc.) as
    JSON. Not every game has this — older/lower-profile games may not, in
    which case we keep the box score and skip PBP/shot rows for that game.
"""

import re
import time
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Game, PlayByPlayEvent, PlayerGameStats, ShotEvent
from app.scrapers.common import (
    discard_pbp_if_score_mismatch,
    find_or_create_competition,
    find_or_create_player,
    find_or_create_team,
    slug_for_hebrew_team,
    stable_hash,
)

BASE_URL = "https://basket.co.il"
SEGEV_BASE_URL = "https://stats.segevstats.com/realtimestat_heb"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RedPulseAnalytics/1.0; personal fan-built analytics tool)"}

BOX_SCORE_COLUMNS = [
    "jersey", "name", "starter", "minutes", "points",
    "fg2", "fg2_pct", "fg3", "fg3_pct", "ft", "ft_pct",
    # Site's own header order is "הג" (defense) then "הת" (offense) — i.e.
    # DREB before OREB, the opposite of what the abbreviations suggest at a
    # glance. Verified against segevstats' player-level rebound totals.
    "dreb", "oreb", "reb", "fouls", "fouls_drawn", "steals",
    "turnovers", "assists", "blocks_made", "blocks_against", "valuation", "plus_minus",
]

# Shot zones classified from real coordX/coordY (basket at x=~735, y=~112 in
# segevstats' coordinate system; scale ~85 units/meter) plus the shot `type`
# segevstats already assigns (dunk/lay-up/jump-shot/allyhoop).
SEGEV_BASKET_X = 735
SEGEV_BASKET_Y = 112
SEGEV_UNITS_PER_METER = 85


class WinnerLeagueScraper:
    def __init__(self, client: Optional[httpx.Client] = None):
        self.client = client or httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)

    def sync(self, db: Session, cyear: int = 2026, max_games: Optional[int] = None, delay: float = 0.4) -> int:
        games = self.fetch_schedule(cyear)
        if max_games is not None:
            games = games[:max_games]

        find_or_create_competition(db, "WINNER_LEAGUE", "Winner League", f"{cyear - 1}-{str(cyear)[-2:]}")
        db.commit()

        synced = 0
        for g in games:
            game_id = f"WL_{g['game_zone_id']}"
            if db.get(Game, game_id):
                continue
            try:
                if self._sync_one_game(db, g, cyear, game_id):
                    db.commit()
                    synced += 1
            except (httpx.HTTPError, KeyError, ValueError, AttributeError, SQLAlchemyError):
                db.rollback()
            time.sleep(delay)
        return synced

    def fetch_schedule(self, cyear: int) -> list[dict]:
        resp = self.client.get(
            f"{BASE_URL}/results.asp",
            params={"cYear": cyear, "Board": 5, "RoundNumber": 0, "TeamId": 0},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        schedule_table = None
        for table in soup.find_all("table"):
            if "מארחת" in table.get_text():
                schedule_table = table
                break
        if schedule_table is None:
            return []

        games = []
        current_round = None
        for row in schedule_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 1:
                text = cells[0].get_text(strip=True)
                if text.startswith("מחזור"):
                    current_round = text
                continue

            result_link = row.find("a", href=re.compile(r"^game-zone\.asp\?GameId=\d+$"))
            if not result_link:
                continue
            score_match = re.match(r"(\d+)\s*-\s*(\d+)", result_link.get_text(strip=True))
            if not score_match:
                continue  # not yet played

            team_links = row.find_all("a", href=re.compile(r"^team\.asp\?TeamId=\d+"))
            if len(team_links) < 2:
                continue
            home_name = self._team_name_from_link(team_links[0])
            away_name = self._team_name_from_link(team_links[1])

            date_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", cells[0].get_text())
            game_date = (
                datetime(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1)))
                if date_match
                else None
            )

            games.append(
                {
                    "game_zone_id": re.search(r"GameId=(\d+)", result_link["href"]).group(1),
                    "round": current_round,
                    "home_name": home_name,
                    "away_name": away_name,
                    "home_score": int(score_match.group(1)),
                    "away_score": int(score_match.group(2)),
                    "game_date": game_date,
                }
            )
        return games

    def _team_name_from_link(self, link) -> str:
        img = link.find("img")
        if img and img.get("alt"):
            return img["alt"].strip()
        return link.get_text(strip=True)

    def _sync_one_game(self, db: Session, g: dict, cyear: int, game_id: str) -> bool:
        resp = self.client.get(f"{BASE_URL}/game-zone.asp", params={"GameId": g["game_zone_id"]})
        resp.raise_for_status()
        page_html = resp.text

        box_score = self._parse_box_score(page_html)
        if box_score is None:
            return False

        home_slug, home_en = slug_for_hebrew_team(g["home_name"])
        away_slug, away_en = slug_for_hebrew_team(g["away_name"])
        if home_slug not in box_score or away_slug not in box_score:
            return False  # box score tables didn't match either scheduled team; skip rather than mislabel

        home_team = find_or_create_team(db, home_slug, home_en, home_en, "WINNER_LEAGUE", home_slug == "HAPOEL_JLM")
        away_team = find_or_create_team(db, away_slug, away_en, away_en, "WINNER_LEAGUE", away_slug == "HAPOEL_JLM")
        home_rows = box_score[home_slug]
        away_rows = box_score[away_slug]

        game = Game(
            id=game_id,
            competition_id="WINNER_LEAGUE",
            season=f"{cyear - 1}-{str(cyear)[-2:]}",
            round=g["round"],
            game_date=g["game_date"] or datetime(cyear - 1, 10, 1),
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            home_score=sum(int(r["points"]) for r in home_rows),
            away_score=sum(int(r["points"]) for r in away_rows),
            is_synced=True,
            raw_pbp_available=False,
        )
        db.add(game)
        db.flush()

        self._persist_box_score(db, game, home_team.id, home_rows)
        self._persist_box_score(db, game, away_team.id, away_rows)

        segev_id = self._extract_segev_game_id(page_html)
        if segev_id:
            try:
                home_starter_jerseys = {r["jersey"] for r in home_rows if r["starter"] == "*"}
                away_starter_jerseys = {r["jersey"] for r in away_rows if r["starter"] == "*"}
                self._sync_play_by_play(db, game, home_team.id, away_team.id, segev_id, home_starter_jerseys, away_starter_jerseys)
                game.raw_pbp_available = True
            except (httpx.HTTPError, KeyError, ValueError):
                pass  # box score already saved; PBP is best-effort

        return True

    def fetch_box_score(self, game_zone_id: str) -> Optional[dict[str, list[dict]]]:
        resp = self.client.get(f"{BASE_URL}/game-zone.asp", params={"GameId": game_zone_id})
        resp.raise_for_status()
        return self._parse_box_score(resp.text)

    def _parse_box_score(self, page_html: str) -> Optional[dict[str, list[dict]]]:
        """Returns {team_slug: rows}. Tables are matched to a team by the
        Hebrew name in their own caption row rather than assumed left/right
        position — the page doesn't reliably put the home team's table first."""
        soup = BeautifulSoup(page_html, "html.parser")
        tables = [
            t for t in soup.find_all("table")
            if "stats_tbl" in t.get("class", []) and "categories" not in t.get("class", [])
        ]
        if len(tables) < 2:
            return None  # box score not published for this game

        by_slug: dict[str, list[dict]] = {}
        for table in tables[:2]:
            caption_row = table.find("tr")
            if not caption_row:
                continue
            caption = caption_row.get_text(" ", strip=True)
            slug, _ = slug_for_hebrew_team(caption)
            by_slug[slug] = self._parse_team_table(table)
        return by_slug if len(by_slug) == 2 else None

    def _parse_team_table(self, table) -> list[dict]:
        rows = []
        for row in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) != len(BOX_SCORE_COLUMNS):
                continue
            record = dict(zip(BOX_SCORE_COLUMNS, cells))
            try:
                jersey = int(record["jersey"])
            except ValueError:
                continue  # header row, or a "team"/"total" summary row
            if not record["name"]:
                continue
            record["jersey"] = jersey
            rows.append(record)
        return rows

    def _persist_box_score(self, db: Session, game: Game, team_id: str, rows: list[dict]) -> dict[int, str]:
        # Keyed by name, not jersey number: a merged franchise (e.g. this
        # season's Beer Sheva/Dimona combine) can have two different players
        # wearing the same number, so jersey alone isn't a safe identity key.
        jersey_to_player_id: dict[int, str] = {}
        for r in rows:
            player = find_or_create_player(
                db, team_id, f"WL_{team_id}_{stable_hash(r['name'])}", r["name"], jersey=r["jersey"]
            )
            jersey_to_player_id[r["jersey"]] = player.id

            fg2m, fg2a = _split_made_attempted(r["fg2"])
            fg3m, fg3a = _split_made_attempted(r["fg3"])
            ftm, fta = _split_made_attempted(r["ft"])
            db.add(
                PlayerGameStats(
                    id=f"{game.id}_STAT_{player.id}",
                    game_id=game.id,
                    player_id=player.id,
                    team_id=team_id,
                    minutes_played=_parse_minutes(r["minutes"]),
                    points=int(r["points"] or 0),
                    fgm=fg2m + fg3m,
                    fga=fg2a + fg3a,
                    fg2m=fg2m, fg2a=fg2a, fg3m=fg3m, fg3a=fg3a,
                    ftm=ftm, fta=fta,
                    oreb=int(r["oreb"] or 0), dreb=int(r["dreb"] or 0), reb=int(r["reb"] or 0),
                    assists=int(r["assists"] or 0),
                    steals=int(r["steals"] or 0),
                    turnovers=int(r["turnovers"] or 0),
                    blocks=int(r["blocks_made"] or 0),
                    personal_fouls=int(r["fouls"] or 0),
                    fouls_drawn=int(r["fouls_drawn"] or 0),
                    plus_minus=int(r["plus_minus"] or 0),
                    valuation=int(r["valuation"] or 0),
                )
            )
        return jersey_to_player_id

    def find_segev_game_id(self, game_zone_id: str) -> Optional[str]:
        resp = self.client.get(f"{BASE_URL}/game-zone.asp", params={"GameId": game_zone_id})
        resp.raise_for_status()
        return self._extract_segev_game_id(resp.text)

    def _extract_segev_game_id(self, page_html: str) -> Optional[str]:
        match = re.search(r"segevstats\.com/realtimestat_heb/index\.php\?game_id=(\d+)", page_html)
        return match.group(1) if match else None

    def _sync_play_by_play(
        self, db: Session, game: Game, home_team_id: str, away_team_id: str, segev_id: str,
        home_starter_jerseys: Optional[set] = None, away_starter_jerseys: Optional[set] = None,
    ) -> None:
        resp = self.client.get(f"{SEGEV_BASE_URL}/get_team_action.php", params={"game_id": segev_id})
        resp.raise_for_status()
        result = resp.json()["result"]
        game_info = result["gameInfo"]

        segev_home_id = str(game_info["homeTeam"]["id"])
        segev_away_id = str(game_info["awayTeam"]["id"])
        team_id_map = {segev_home_id: home_team_id, segev_away_id: away_team_id}

        player_id_map: dict[int, str] = {}
        # Not every game's action log carries an explicit "IN" event for the
        # five players who started (some do, most don't) — seed the initial
        # lineup from the box score's starter flag, matched by jersey number,
        # rather than relying on that.
        starting_lineup: dict[str, set] = {home_team_id: set(), away_team_id: set()}
        starter_jerseys_by_team = {home_team_id: home_starter_jerseys or set(), away_team_id: away_starter_jerseys or set()}
        for side, our_team_id in ((game_info["homeTeam"], home_team_id), (game_info["awayTeam"], away_team_id)):
            for p in side["players"]:
                name = f"{p['firstName'].title()} {p['lastName'].title()}"
                player = find_or_create_player(
                    db, our_team_id, f"WL_{p['id']}", name, jersey=p.get("jerseyNumber")
                )
                player_id_map[int(p["id"])] = player.id
                if p.get("jerseyNumber") in starter_jerseys_by_team[our_team_id]:
                    starting_lineup[our_team_id].add(player.id)

        lineup: dict[str, set] = {home_team_id: set(starting_lineup[home_team_id]), away_team_id: set(starting_lineup[away_team_id])}
        running_score = {home_team_id: 0, away_team_id: 0}
        last_made_shot: dict[str, ShotEvent] = {}
        last_made_shot_pbp: dict[str, PlayByPlayEvent] = {}
        pbp_counter = 0
        shot_counter = 0

        for action in result["actions"]:
            team_id = team_id_map.get(str(action.get("teamId")))
            player_id = player_id_map.get(action.get("playerId"))
            params = action.get("parameters", {})
            atype = action["type"]

            if atype == "substitution" and team_id and player_id:
                if params.get("playerIn") is not None:
                    lineup[team_id].add(player_id)
                elif params.get("playerOut") is not None:
                    lineup[team_id].discard(player_id)
                continue

            if atype not in _EVENT_TYPE_MAP or not team_id:
                continue

            if atype == "shot" and params.get("made") == "made":
                running_score[team_id] += params.get("points", 0)
            elif atype == "freeThrow" and params.get("made") == "made":
                running_score[team_id] += 1

            # segevstats logs an assist as its own event immediately after the
            # made shot it set up; attach it to that shot rather than storing
            # it as a standalone row.
            if atype == "assist" and player_id and team_id in last_made_shot:
                last_made_shot[team_id].is_assisted = True
                last_made_shot[team_id].assister_id = player_id
                last_made_shot_pbp[team_id].secondary_player_id = player_id
                continue

            pbp_counter += 1
            pbp_event = PlayByPlayEvent(
                id=f"{game.id}_PBP_{pbp_counter:04d}",
                game_id=game.id,
                period=action.get("quarter", 1),
                game_clock=action.get("quarterTime", "00:00"),
                event_type=_EVENT_TYPE_MAP[atype],
                acting_team_id=team_id,
                primary_player_id=player_id,
                secondary_player_id=None,
                home_score=running_score[home_team_id],
                away_score=running_score[away_team_id],
                current_lineup_home=list(lineup[home_team_id])[:5],
                current_lineup_away=list(lineup[away_team_id])[:5],
            )
            db.add(pbp_event)

            if atype == "shot" and player_id:
                x, y = params.get("coordX"), params.get("coordY")
                if x is not None and y is not None:
                    shot_counter += 1
                    shot_event = ShotEvent(
                        id=f"{game.id}_SHOT_{shot_counter:04d}",
                        game_id=game.id,
                        player_id=player_id,
                        team_id=team_id,
                        period=action.get("quarter", 1),
                        game_clock=action.get("quarterTime", "00:00"),
                        x_coord=x,
                        y_coord=y,
                        shot_type=_classify_shot_zone(x, y, params),
                        is_made=params.get("made") == "made",
                        is_assisted=False,
                        assister_id=None,
                    )
                    db.add(shot_event)
                    if shot_event.is_made:
                        last_made_shot[team_id] = shot_event
                        last_made_shot_pbp[team_id] = pbp_event

        db.flush()
        discarded = discard_pbp_if_score_mismatch(
            db, game.id, running_score[home_team_id], running_score[away_team_id], game.home_score, game.away_score
        )
        if discarded:
            raise ValueError(
                f"segevstats PBP for game {game.id} reconstructs to "
                f"{running_score[home_team_id]}-{running_score[away_team_id]}, "
                f"doesn't match box score {game.home_score}-{game.away_score} "
                "(a player is likely missing from segevstats' own roster for this game)"
            )


_EVENT_TYPE_MAP = {
    "shot": "SHOT",
    "freeThrow": "FREE_THROW",
    "rebound": "REBOUND",
    "turnover": "TURNOVER",
    "foul": "FOUL",
    "steal": "STEAL",
    "block": "BLOCK",
    "assist": "ASSIST",
}


def _split_made_attempted(value: str) -> tuple[int, int]:
    if not value or "/" not in value:
        return 0, 0
    made, attempted = value.split("/")
    return int(made), int(attempted)


def _parse_minutes(value: str) -> float:
    if not value:
        return 0.0
    if ":" in value:
        minutes, seconds = value.split(":")
        return round(int(minutes) + int(seconds) / 60, 2)
    try:
        return float(value)
    except ValueError:
        return 0.0


def _classify_shot_zone(x: float, y: float, params: dict) -> str:
    dist_m = ((x - SEGEV_BASKET_X) ** 2 + (y - SEGEV_BASKET_Y) ** 2) ** 0.5 / SEGEV_UNITS_PER_METER
    shot_kind = params.get("type", "")
    points = params.get("points", 2)

    if points == 3:
        is_corner = y < 220 and abs(x - SEGEV_BASKET_X) > 460
        return "Corner-3" if is_corner else "Above-the-Break-3"
    if shot_kind in ("dunk", "lay-up", "allyhoop") or dist_m < 1.5:
        return "Rim"
    if dist_m < 5.8:
        return "Paint"
    return "Mid-Range"
