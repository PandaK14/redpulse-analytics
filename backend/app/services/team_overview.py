"""Team-level orchestration: pulls raw box-score rows for a team (and its
opponents) and composes them with the formulas in four_factors.py /
advanced_stats.py. No math lives here directly — see those two modules.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Player, PlayerGameStats, Team
from app.services.advanced_stats import (
    STAT_FIELDS,
    estimated_possessions,
    net_rating,
    offensive_rating,
    defensive_rating,
    pace,
    player_season_profile,
    sum_stats,
)
from app.services.four_factors import four_factors


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
            {"game": game, "opponent_id": opponent_id, "team": sum_stats(team_rows), "opponent": sum_stats(opp_rows)}
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
    team_poss = sum(estimated_possessions(r["team"]["fga"], r["team"]["fta"], r["team"]["oreb"], r["team"]["turnovers"]) for r in rows)
    opp_poss = sum(estimated_possessions(r["opponent"]["fga"], r["opponent"]["fta"], r["opponent"]["oreb"], r["opponent"]["turnovers"]) for r in rows)
    team_minutes_total = games_played * 200

    ortg = offensive_rating(team_points, team_poss)
    drtg = defensive_rating(opp_points, opp_poss)

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
        "net_rating": round(net_rating(ortg, drtg), 1),
        "pace": round(pace(team_poss, opp_poss, team_minutes_total), 1),
        "four_factors": four_factors(team_totals, opp_totals),
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
    summary_fields = [
        "player_id", "name", "position", "jersey_number",
        "games_played", "mpg", "ppg", "rpg", "apg", "ts_pct", "usg_pct", "ast_to",
    ]
    players = db.query(Player).filter(Player.team_id == team_id).all()
    result = []
    for player in players:
        profile = player_season_profile(db, player.id)
        if profile is None:
            continue
        result.append({k: profile[k] for k in summary_fields})
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
