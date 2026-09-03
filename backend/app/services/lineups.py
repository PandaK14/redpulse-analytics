"""Lineup/stint analytics: reconstructs which 5 players were on the court
for a team at any point in a game from PlayByPlayEvent's lineup snapshots,
and aggregates those "stints" into lineup combination tables and on/off
splits.

Rebound offense/defense isn't distinguished in event_type (see the model's
own comment — it's a generic 'REBOUND', matching the PRD's schema), which
the possession formula needs. Rather than change the schema or re-scrape,
we classify it here: a rebound event always immediately follows the missed
shot/free-throw that produced it, so tracking "which team took the last
shot/FT" while walking events tells us offensive (same team) vs. defensive
(other team) rebound with no new data needed.
"""

from itertools import combinations
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, PlayByPlayEvent, Player
from app.services.advanced_stats import defensive_rating, estimated_possessions, net_rating, offensive_rating

PERIOD_SECONDS = 600  # FIBA quarter
OT_SECONDS = 300  # FIBA overtime period


def _elapsed_seconds(period: int, game_clock: str) -> int:
    minutes_str, _, seconds_str = game_clock.partition(":")
    clock_remaining = int(minutes_str or 0) * 60 + int(seconds_str or 0)
    if period <= 4:
        period_start = (period - 1) * PERIOD_SECONDS
        period_length = PERIOD_SECONDS
    else:
        period_start = 4 * PERIOD_SECONDS + (period - 5) * OT_SECONDS
        period_length = OT_SECONDS
    return period_start + (period_length - clock_remaining)


def _new_tally() -> dict:
    return {"fga": 0, "fta": 0, "oreb": 0, "tov": 0, "points": 0}


def _reconstruct_game_stints(
    events: list[PlayByPlayEvent], team_id: str, home_team_id: str, away_team_id: str,
    valid_player_ids: Optional[set] = None,
) -> list[dict]:
    is_home = team_id == home_team_id
    opponent_id = away_team_id if is_home else home_team_id

    stints: list[dict] = []
    current_lineup: Optional[tuple] = None
    stint_start_sec = 0
    team_tally = _new_tally()
    opp_tally = _new_tally()
    last_home_score = 0
    last_away_score = 0
    last_shot_team: Optional[str] = None

    def close_stint(end_sec: int) -> None:
        if current_lineup is None:
            return
        stints.append(
            {
                "lineup": current_lineup,
                "minutes": (end_sec - stint_start_sec) / 60,
                "team_points": team_tally["points"],
                "opp_points": opp_tally["points"],
                "team_poss": estimated_possessions(team_tally["fga"], team_tally["fta"], team_tally["oreb"], team_tally["tov"]),
                "opp_poss": estimated_possessions(opp_tally["fga"], opp_tally["fta"], opp_tally["oreb"], opp_tally["tov"]),
            }
        )

    for event in events:
        raw_lineup = event.current_lineup_home if is_home else event.current_lineup_away
        # Defends against a source data-quality issue (a coach/bench pseudo-id,
        # or — rarer — a genuine cross-team player-id collision in the source
        # feed) leaking a non-roster id into the lineup snapshot: any such
        # entry drops the snapshot below 5 players, which the final filter
        # below already excludes, rather than silently mislabeling a stint.
        if valid_player_ids is not None:
            raw_lineup = [p for p in raw_lineup if p in valid_player_ids]
        lineup = tuple(sorted(raw_lineup))
        sec = _elapsed_seconds(event.period, event.game_clock)

        if current_lineup is None:
            current_lineup = lineup
            stint_start_sec = sec
        elif lineup != current_lineup and lineup:
            close_stint(sec)
            current_lineup = lineup
            stint_start_sec = sec
            team_tally = _new_tally()
            opp_tally = _new_tally()

        acting = event.acting_team_id
        tally = team_tally if acting == team_id else (opp_tally if acting == opponent_id else None)
        if tally is not None:
            if event.event_type == "SHOT":
                tally["fga"] += 1
                last_shot_team = acting
            elif event.event_type == "FREE_THROW":
                tally["fta"] += 1
                last_shot_team = acting
            elif event.event_type == "TURNOVER":
                tally["tov"] += 1
            elif event.event_type == "REBOUND" and acting == last_shot_team:
                tally["oreb"] += 1

        home_delta = event.home_score - last_home_score
        away_delta = event.away_score - last_away_score
        if is_home:
            team_tally["points"] += home_delta
            opp_tally["points"] += away_delta
        else:
            team_tally["points"] += away_delta
            opp_tally["points"] += home_delta
        last_home_score, last_away_score = event.home_score, event.away_score

    if events:
        close_stint(_elapsed_seconds(events[-1].period, events[-1].game_clock))

    return [s for s in stints if len(s["lineup"]) == 5]


def team_lineup_stints(db: Session, team_id: str) -> list[dict]:
    """All 5-man stints (across every game with play-by-play) for a team."""
    games = db.query(Game).filter(
        (Game.home_team_id == team_id) | (Game.away_team_id == team_id),
        Game.raw_pbp_available.is_(True),
    ).all()
    valid_player_ids = {p.id for p in db.query(Player.id).filter(Player.team_id == team_id).all()}

    all_stints = []
    for game in games:
        events = (
            db.query(PlayByPlayEvent)
            .filter(PlayByPlayEvent.game_id == game.id)
            .order_by(PlayByPlayEvent.id)
            .all()
        )
        if not events or not _lineup_tracking_is_reliable(events, team_id, game.home_team_id, valid_player_ids):
            # A player entirely missing from the source's own roster for this
            # game (a real, if rare, third-party data gap) leaves that side's
            # lineup snapshot stuck at 4 players for as long as they're on
            # court. The scoring/shot data is still fine, but the 5-man
            # filter in _reconstruct_game_stints would then silently drop
            # most of the game's stints — and their points — rather than
            # just the untracked player's minutes. Skip the whole game's
            # lineup data instead of serving a badly truncated result.
            continue
        all_stints.extend(_reconstruct_game_stints(events, team_id, game.home_team_id, game.away_team_id, valid_player_ids))
    return all_stints


def _lineup_tracking_is_reliable(
    events: list[PlayByPlayEvent], team_id: str, home_team_id: str, valid_player_ids: set, threshold: float = 0.8
) -> bool:
    is_home = team_id == home_team_id
    complete = sum(
        1
        for e in events
        if len([p for p in (e.current_lineup_home if is_home else e.current_lineup_away) if p in valid_player_ids]) == 5
    )
    return complete / len(events) >= threshold


def _empty_bucket() -> dict:
    return {"minutes": 0.0, "team_points": 0, "opp_points": 0, "team_poss": 0.0, "opp_poss": 0.0}


def _accumulate(bucket: dict, stint: dict) -> None:
    bucket["minutes"] += stint["minutes"]
    bucket["team_points"] += stint["team_points"]
    bucket["opp_points"] += stint["opp_points"]
    bucket["team_poss"] += stint["team_poss"]
    bucket["opp_poss"] += stint["opp_poss"]


def _bucket_ratings(bucket: dict) -> dict:
    ortg = offensive_rating(bucket["team_points"], bucket["team_poss"])
    drtg = defensive_rating(bucket["opp_points"], bucket["opp_poss"])
    return {"ortg": round(ortg, 1), "drtg": round(drtg, 1), "net_rating": round(net_rating(ortg, drtg), 1)}


def lineup_table(db: Session, team_id: str, size: int = 5, min_minutes: float = 0.0) -> list[dict]:
    """5-man lineups by default; pass size=3 or size=2 for the sub-combination
    tables (every 5-man stint counts toward each of its N-man subsets)."""
    stints = team_lineup_stints(db, team_id)
    if size not in (5, 4, 3, 2, 1):
        raise ValueError("size must be between 1 and 5")

    if size != 5:
        expanded = []
        for s in stints:
            for combo in combinations(s["lineup"], size):
                expanded.append({**s, "lineup": combo})
        stints = expanded

    players = {p.id: p.name for p in db.query(Player).filter(Player.team_id == team_id).all()}
    buckets: dict[tuple, dict] = {}
    for s in stints:
        bucket = buckets.setdefault(s["lineup"], _empty_bucket())
        _accumulate(bucket, s)

    rows = []
    for lineup_key, bucket in buckets.items():
        if bucket["minutes"] < min_minutes:
            continue
        rows.append(
            {
                "player_ids": list(lineup_key),
                "player_names": [players.get(pid, pid) for pid in lineup_key],
                "minutes": round(bucket["minutes"], 1),
                "possessions": round(bucket["team_poss"], 1),
                "plus_minus": bucket["team_points"] - bucket["opp_points"],
                **_bucket_ratings(bucket),
            }
        )
    rows.sort(key=lambda r: r["minutes"], reverse=True)
    return rows


def on_off_table(db: Session, team_id: str) -> list[dict]:
    stints = team_lineup_stints(db, team_id)
    roster = db.query(Player).filter(Player.team_id == team_id).all()

    rows = []
    for player in roster:
        on, off = _empty_bucket(), _empty_bucket()
        for s in stints:
            _accumulate(on if player.id in s["lineup"] else off, s)

        if on["minutes"] == 0 and off["minutes"] == 0:
            continue

        net_on = _bucket_ratings(on)["net_rating"] if on["minutes"] else None
        net_off = _bucket_ratings(off)["net_rating"] if off["minutes"] else None
        rows.append(
            {
                "player_id": player.id,
                "name": player.name,
                "minutes_on": round(on["minutes"], 1),
                "minutes_off": round(off["minutes"], 1),
                "net_rating_on": net_on,
                "net_rating_off": net_off,
                "on_off_diff": round(net_on - net_off, 1) if net_on is not None and net_off is not None else None,
            }
        )

    rows.sort(key=lambda r: (r["on_off_diff"] is None, -(r["on_off_diff"] or 0)))
    return rows
