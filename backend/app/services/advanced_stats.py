"""Possession/rating math and individual player efficiency metrics.

The rating functions (`offensive_rating`, `defensive_rating`, `net_rating`,
`estimated_possessions`) take plain numbers rather than a team dict so they
can be reused at any granularity — a full season, a competition split, or a
single lineup stint (see `services/lineups.py`).
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Player, PlayerGameStats, Team

STAT_FIELDS = [
    "points", "fgm", "fga", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
    "oreb", "dreb", "reb", "assists", "steals", "turnovers", "blocks",
    "personal_fouls", "fouls_drawn",
]


def sum_stats(rows: list[PlayerGameStats]) -> dict:
    return {field: sum(getattr(r, field) for r in rows) for field in STAT_FIELDS}


def estimated_possessions(fga: float, fta: float, oreb: float, tov: float) -> float:
    # Floored at 0: the formula is calibrated for full-game/season totals and
    # can dip slightly negative over a very short window (e.g. a missed free
    # throw immediately offensive-rebounded, in a stint just a few seconds
    # long) — never a meaningful outcome for an actual count of possessions.
    return max(0.0, fga + 0.44 * fta - oreb + tov)


def offensive_rating(points: float, possessions: float) -> float:
    return 100 * points / possessions if possessions else 0.0


def defensive_rating(opp_points: float, opp_possessions: float) -> float:
    return 100 * opp_points / opp_possessions if opp_possessions else 0.0


def net_rating(ortg: float, drtg: float) -> float:
    return ortg - drtg


def pace(team_poss: float, opp_poss: float, team_minutes_total: float) -> float:
    # 5 players x 40 FIBA minutes per game = 200 "team minutes" per game.
    return 40 * ((team_poss + opp_poss) / 2) / (team_minutes_total / 5) if team_minutes_total else 0.0


def true_shooting_pct(points: float, fga: float, fta: float) -> float:
    denom = 2 * (fga + 0.44 * fta)
    return points / denom if denom else 0.0


def usage_pct(
    player_fga: float, player_fta: float, player_tov: float, player_minutes: float,
    team_fga: float, team_fta: float, team_tov: float,
) -> float:
    denom = player_minutes * (team_fga + 0.44 * team_fta + team_tov)
    if not denom:
        return 0.0
    return 100 * (player_fga + 0.44 * player_fta + player_tov) * 40 / denom


def assist_to_turnover(assists: float, turnovers: float) -> float:
    return assists / turnovers if turnovers else assists


def _rolling_form(game_log: list[dict], window: int = 5) -> list[dict]:
    rolling = []
    for i in range(len(game_log)):
        chunk = game_log[max(0, i - window + 1) : i + 1]
        pts = sum(g["points"] for g in chunk)
        fga = sum(g["fg2a"] + g["fg3a"] for g in chunk)
        fta = sum(g["fta"] for g in chunk)
        rolling.append(
            {
                "game_date": game_log[i]["game_date"],
                "points": game_log[i]["points"],
                "rolling_ppg": round(pts / len(chunk), 1),
                "rolling_ts_pct": round(true_shooting_pct(pts, fga, fta), 4),
            }
        )
    return rolling


def player_season_profile(db: Session, player_id: str) -> Optional[dict]:
    """Season averages, advanced metrics, full game log, and rolling form for
    one player. Backs both the roster table (summary fields only) and the
    player detail endpoint (everything)."""
    player = db.get(Player, player_id)
    if player is None:
        return None

    game_rows = db.query(PlayerGameStats).filter(PlayerGameStats.player_id == player_id).all()
    if not game_rows:
        return None

    gp = len(game_rows)
    totals = {f: sum(float(getattr(r, f)) for r in game_rows) for f in STAT_FIELDS}
    minutes_total = sum(float(r.minutes_played) for r in game_rows)

    usg_samples = []
    game_log = []
    for r in game_rows:
        team_stats = sum_stats(db.query(PlayerGameStats).filter_by(game_id=r.game_id, team_id=r.team_id).all())
        if r.minutes_played:
            usg_samples.append(
                usage_pct(r.fga, r.fta, r.turnovers, float(r.minutes_played), team_stats["fga"], team_stats["fta"], team_stats["turnovers"])
            )

        game = db.get(Game, r.game_id)
        opponent_id = game.away_team_id if game.home_team_id == r.team_id else game.home_team_id
        opponent = db.get(Team, opponent_id)
        opp_points = sum_stats(db.query(PlayerGameStats).filter_by(game_id=r.game_id, team_id=opponent_id).all())["points"]

        game_log.append(
            {
                "game_id": r.game_id,
                "game_date": game.game_date.isoformat(),
                "opponent_name": opponent.name if opponent else opponent_id,
                "result": "W" if team_stats["points"] > opp_points else "L",
                "minutes_played": float(r.minutes_played),
                "points": r.points,
                "reb": r.reb,
                "assists": r.assists,
                "fg2m": r.fg2m, "fg2a": r.fg2a, "fg3m": r.fg3m, "fg3a": r.fg3a,
                "ftm": r.ftm, "fta": r.fta,
                "steals": r.steals, "turnovers": r.turnovers, "blocks": r.blocks,
                "valuation": r.valuation,
            }
        )

    game_log.sort(key=lambda g: g["game_date"])

    return {
        "player_id": player.id,
        "name": player.name,
        "position": player.position,
        "jersey_number": player.jersey_number,
        "height_cm": player.height_cm,
        "team_id": player.team_id,
        "games_played": gp,
        "mpg": round(minutes_total / gp, 1),
        "ppg": round(totals["points"] / gp, 1),
        "rpg": round(totals["reb"] / gp, 1),
        "apg": round(totals["assists"] / gp, 1),
        "ts_pct": round(true_shooting_pct(totals["points"], totals["fga"], totals["fta"]), 4),
        "usg_pct": round(sum(usg_samples) / len(usg_samples), 1) if usg_samples else 0.0,
        "ast_to": round(assist_to_turnover(totals["assists"], totals["turnovers"]), 2),
        "game_log": game_log,
        "rolling_form": _rolling_form(game_log),
    }
