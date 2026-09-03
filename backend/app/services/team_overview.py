"""Lightweight analytics used to power the first frontend preview.

This computes Four Factors / ratings / usage directly from box-score rows
using the formulas in the PRD. It's intentionally minimal (no lineup or
shot-chart analytics yet) — Phase 2 will replace this with the full
four_factors.py / advanced_stats.py services and formal Pydantic schemas.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Player, PlayerGameStats, Team

STAT_FIELDS = [
    "points", "fgm", "fga", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
    "oreb", "dreb", "reb", "assists", "steals", "turnovers", "blocks",
    "personal_fouls", "fouls_drawn",
]


def _sum_stats(rows: list[PlayerGameStats]) -> dict:
    return {field: sum(getattr(r, field) for r in rows) for field in STAT_FIELDS}


def _possessions(stats: dict) -> float:
    return stats["fga"] + 0.44 * stats["fta"] - stats["oreb"] + stats["turnovers"]


def _four_factors(team: dict, opp: dict) -> dict:
    fga = team["fga"] or 1
    return {
        "efg_pct": round((team["fgm"] + 0.5 * team["fg3m"]) / fga, 4),
        "tov_pct": round(team["turnovers"] / (fga + 0.44 * team["fta"] + team["turnovers"] or 1), 4),
        "orb_pct": round(team["oreb"] / ((team["oreb"] + opp["dreb"]) or 1), 4),
        "ftr": round(team["fta"] / fga, 4),
    }


def team_game_rows(db: Session, team_id: str, competition_id: Optional[str] = None) -> list[dict]:
    query = db.query(Game).filter(
        ((Game.home_team_id == team_id) | (Game.away_team_id == team_id)),
        Game.is_synced.is_(True),
    )
    if competition_id and competition_id != "ALL":
        query = query.filter(Game.competition_id == competition_id)

    rows = []
    for game in query.all():
        opponent_id = game.away_team_id if game.home_team_id == team_id else game.home_team_id
        team_rows = db.query(PlayerGameStats).filter_by(game_id=game.id, team_id=team_id).all()
        opp_rows = db.query(PlayerGameStats).filter_by(game_id=game.id, team_id=opponent_id).all()
        if not team_rows or not opp_rows:
            continue  # box score not (yet) available for this game — exclude rather than count it as 0-0
        rows.append(
            {"game": game, "opponent_id": opponent_id, "team": _sum_stats(team_rows), "opponent": _sum_stats(opp_rows)}
        )
    return rows


def team_overview(db: Session, team_id: str, competition_id: Optional[str] = None) -> dict:
    rows = team_game_rows(db, team_id, competition_id)
    games_played = len(rows)
    if games_played == 0:
        return {"games_played": 0}

    wins = sum(1 for r in rows if r["team"]["points"] > r["opponent"]["points"])
    losses = games_played - wins

    team_points = sum(r["team"]["points"] for r in rows)
    opp_points = sum(r["opponent"]["points"] for r in rows)
    team_poss = sum(_possessions(r["team"]) for r in rows)
    opp_poss = sum(_possessions(r["opponent"]) for r in rows)
    team_minutes_total = games_played * 200  # 5 players x 40 FIBA minutes per game

    ortg = 100 * team_points / team_poss if team_poss else 0
    drtg = 100 * opp_points / opp_poss if opp_poss else 0
    pace = 40 * ((team_poss + opp_poss) / 2) / (team_minutes_total / 5) if team_minutes_total else 0

    team_totals = {f: sum(r["team"][f] for r in rows) for f in STAT_FIELDS}
    opp_totals = {f: sum(r["opponent"][f] for r in rows) for f in STAT_FIELDS}

    return {
        "games_played": games_played,
        "wins": wins,
        "losses": losses,
        "points_for_avg": round(team_points / games_played, 1),
        "points_against_avg": round(opp_points / games_played, 1),
        "ortg": round(ortg, 1),
        "drtg": round(drtg, 1),
        "net_rating": round(ortg - drtg, 1),
        "pace": round(pace, 1),
        "four_factors": _four_factors(team_totals, opp_totals),
    }


def competition_average_four_factors(db: Session, competition_id: str) -> dict:
    team_ids = [t.id for t in db.query(Team).filter(Team.competition_id == competition_id).all()]
    factor_sums = {"efg_pct": 0.0, "tov_pct": 0.0, "orb_pct": 0.0, "ftr": 0.0}
    counted = 0
    for team_id in team_ids:
        overview = team_overview(db, team_id, competition_id)
        if overview.get("games_played"):
            counted += 1
            for k in factor_sums:
                factor_sums[k] += overview["four_factors"][k]
    if not counted:
        return factor_sums
    return {k: round(v / counted, 4) for k, v in factor_sums.items()}


def team_roster_with_averages(db: Session, team_id: str) -> list[dict]:
    players = db.query(Player).filter(Player.team_id == team_id).all()
    result = []
    for player in players:
        game_rows = (
            db.query(PlayerGameStats)
            .filter(PlayerGameStats.player_id == player.id)
            .all()
        )
        if not game_rows:
            continue

        gp = len(game_rows)
        totals = {f: sum(float(getattr(r, f)) for r in game_rows) for f in STAT_FIELDS}
        minutes_total = sum(float(r.minutes_played) for r in game_rows)

        usg_samples = []
        for r in game_rows:
            team_stats = _sum_stats(
                db.query(PlayerGameStats).filter_by(game_id=r.game_id, team_id=r.team_id).all()
            )
            denom = team_stats["fga"] + 0.44 * team_stats["fta"] + team_stats["turnovers"]
            if r.minutes_played and denom:
                usg = 100 * (r.fga + 0.44 * r.fta + r.turnovers) * 40 / (float(r.minutes_played) * denom)
                usg_samples.append(usg)
        usg_pct = sum(usg_samples) / len(usg_samples) if usg_samples else 0

        ts_denom = 2 * (totals["fga"] + 0.44 * totals["fta"])
        ts_pct = totals["points"] / ts_denom if ts_denom else 0
        ast_to = totals["assists"] / totals["turnovers"] if totals["turnovers"] else totals["assists"]

        result.append(
            {
                "player_id": player.id,
                "name": player.name,
                "position": player.position,
                "jersey_number": player.jersey_number,
                "games_played": gp,
                "mpg": round(minutes_total / gp, 1),
                "ppg": round(totals["points"] / gp, 1),
                "rpg": round(totals["reb"] / gp, 1),
                "apg": round(totals["assists"] / gp, 1),
                "ts_pct": round(ts_pct, 4),
                "usg_pct": round(usg_pct, 1),
                "ast_to": round(ast_to, 2),
            }
        )
    result.sort(key=lambda p: p["ppg"], reverse=True)
    return result


def team_games(db: Session, team_id: str) -> list[dict]:
    rows = team_game_rows(db, team_id)
    opponents = {t.id: t for t in db.query(Team).all()}
    games = []
    for r in rows:
        game = r["game"]
        is_home = game.home_team_id == team_id
        team_score = r["team"]["points"]
        opp_score = r["opponent"]["points"]
        games.append(
            {
                "game_id": game.id,
                "competition_id": game.competition_id,
                "round": game.round,
                "game_date": game.game_date.isoformat(),
                "opponent_name": opponents[r["opponent_id"]].name,
                "is_home": is_home,
                "team_score": team_score,
                "opponent_score": opp_score,
                "result": "W" if team_score > opp_score else "L",
            }
        )
    games.sort(key=lambda g: g["game_date"])
    return games
