from datetime import datetime

import pytest

from app.models import Competition, Game, Player, PlayerGameStats, Team
from app.services.advanced_stats import (
    assist_to_turnover,
    defensive_rating,
    estimated_possessions,
    net_rating,
    offensive_rating,
    pace,
    player_season_profile,
    true_shooting_pct,
    usage_pct,
)
from app.services.four_factors import four_factors
from app.services.team_overview import team_overview


# --- Pure-function unit tests: hand-computed expected values --------------

def test_estimated_possessions():
    # 60 FGA + 0.44*20 FTA - 10 OREB + 10 TOV = 60 + 8.8 - 10 + 10 = 68.8
    assert estimated_possessions(fga=60, fta=20, oreb=10, tov=10) == pytest.approx(68.8)


def test_offensive_and_defensive_rating():
    assert offensive_rating(points=80, possessions=68.8) == pytest.approx(100 * 80 / 68.8)
    assert defensive_rating(opp_points=60, opp_possessions=56) == pytest.approx(100 * 60 / 56)
    assert offensive_rating(points=50, possessions=0) == 0.0  # no division by zero


def test_net_rating():
    assert net_rating(ortg=116.28, drtg=107.14) == pytest.approx(9.14, abs=0.01)


def test_pace():
    # 40 * ((68.8 + 56) / 2) / (200 / 5) = 40 * 62.4 / 40 = 62.4
    assert pace(team_poss=68.8, opp_poss=56, team_minutes_total=200) == pytest.approx(62.4)
    assert pace(team_poss=10, opp_poss=10, team_minutes_total=0) == 0.0


def test_true_shooting_pct():
    # 80 points on 60 FGA + 20 FTA: 80 / (2*(60+0.44*20)) = 80 / 137.6
    assert true_shooting_pct(points=80, fga=60, fta=20) == pytest.approx(80 / 137.6)
    assert true_shooting_pct(points=0, fga=0, fta=0) == 0.0


def test_usage_pct():
    # player: 15 FGA, 5 FTA, 3 TOV in 32 minutes; team: 60 FGA, 20 FTA, 10 TOV
    # 100 * (15 + 0.44*5 + 3) * 40 / (32 * (60 + 0.44*20 + 10))
    expected = 100 * (15 + 0.44 * 5 + 3) * 40 / (32 * (60 + 0.44 * 20 + 10))
    assert usage_pct(15, 5, 3, 32, 60, 20, 10) == pytest.approx(expected)
    assert usage_pct(15, 5, 3, 0, 60, 20, 10) == 0.0  # no minutes -> no divide-by-zero


def test_assist_to_turnover():
    assert assist_to_turnover(assists=8, turnovers=4) == 2.0
    assert assist_to_turnover(assists=5, turnovers=0) == 5  # zero turnovers -> falls back to raw assists


def test_four_factors_hand_computed():
    team = {"fgm": 30, "fga": 60, "fg3m": 10, "fta": 20, "turnovers": 10, "oreb": 10}
    opp = {"dreb": 15}
    result = four_factors(team, opp)
    assert result["efg_pct"] == pytest.approx((30 + 0.5 * 10) / 60, abs=1e-4)  # 0.5833...
    assert result["tov_pct"] == pytest.approx(10 / (60 + 0.44 * 20 + 10), abs=1e-4)  # 0.1269...
    assert result["orb_pct"] == pytest.approx(10 / (10 + 15), abs=1e-4)  # 0.4
    assert result["ftr"] == pytest.approx(20 / 60, abs=1e-4)  # 0.3333...


# --- DB-integration tests: a tiny hand-crafted 2-game season ---------------

@pytest.fixture()
def two_game_season(db_session):
    db = db_session
    db.add(Competition(id="TEST_LEAGUE", name="Test League", season="2025-26"))
    db.add(Team(id="TEAM_A", competition_id="TEST_LEAGUE", name="Team A", short_name="A", is_primary_team=True))
    db.add(Team(id="TEAM_B", competition_id="TEST_LEAGUE", name="Team B", short_name="B"))
    db.add(Team(id="TEAM_C", competition_id="TEST_LEAGUE", name="Team C", short_name="C"))
    db.add(Player(id="A1", team_id="TEAM_A", name="Player A1", jersey_number=1))
    db.add(Player(id="B1", team_id="TEAM_B", name="Player B1", jersey_number=1))
    db.add(Player(id="C1", team_id="TEAM_C", name="Player C1", jersey_number=1))
    db.flush()

    # Game 1: TEAM_A (home) 80 vs TEAM_B (away) 60
    db.add(Game(id="G1", competition_id="TEST_LEAGUE", season="2025-26", round="1",
                game_date=datetime(2025, 10, 1), home_team_id="TEAM_A", away_team_id="TEAM_B",
                home_score=80, away_score=60, is_synced=True, raw_pbp_available=False))
    db.add(PlayerGameStats(id="G1_A1", game_id="G1", player_id="A1", team_id="TEAM_A", minutes_played=40,
                            points=80, fgm=30, fga=60, fg2m=20, fg2a=40, fg3m=10, fg3a=20, ftm=10, fta=20,
                            oreb=10, dreb=20, reb=30, assists=20, steals=5, turnovers=10, blocks=2,
                            personal_fouls=15, fouls_drawn=20, plus_minus=20, valuation=40))
    db.add(PlayerGameStats(id="G1_B1", game_id="G1", player_id="B1", team_id="TEAM_B", minutes_played=40,
                            points=60, fgm=20, fga=45, fg2m=15, fg2a=30, fg3m=5, fg3a=15, ftm=15, fta=25,
                            oreb=15, dreb=15, reb=30, assists=10, steals=4, turnovers=15, blocks=1,
                            personal_fouls=20, fouls_drawn=15, plus_minus=-20, valuation=20))

    # Game 2: TEAM_C (home) 70 vs TEAM_A (away) 90
    db.add(Game(id="G2", competition_id="TEST_LEAGUE", season="2025-26", round="2",
                game_date=datetime(2025, 10, 8), home_team_id="TEAM_C", away_team_id="TEAM_A",
                home_score=70, away_score=90, is_synced=True, raw_pbp_available=False))
    db.add(PlayerGameStats(id="G2_A1", game_id="G2", player_id="A1", team_id="TEAM_A", minutes_played=40,
                            points=90, fgm=32, fga=58, fg2m=22, fg2a=38, fg3m=10, fg3a=20, ftm=16, fta=20,
                            oreb=8, dreb=22, reb=30, assists=18, steals=6, turnovers=8, blocks=3,
                            personal_fouls=12, fouls_drawn=18, plus_minus=20, valuation=45))
    db.add(PlayerGameStats(id="G2_C1", game_id="G2", player_id="C1", team_id="TEAM_C", minutes_played=40,
                            points=70, fgm=25, fga=55, fg2m=20, fg2a=40, fg3m=5, fg3a=15, ftm=10, fta=15,
                            oreb=12, dreb=18, reb=30, assists=12, steals=3, turnovers=12, blocks=1,
                            personal_fouls=18, fouls_drawn=20, plus_minus=-20, valuation=18))
    db.commit()
    return db


def test_team_overview_aggregates_across_games(two_game_season):
    db = two_game_season
    overview = team_overview(db, "TEAM_A")

    assert overview["games_played"] == 2
    assert overview["wins"] == 2
    assert overview["losses"] == 0
    assert overview["points_for_avg"] == pytest.approx((80 + 90) / 2)
    assert overview["points_against_avg"] == pytest.approx((60 + 70) / 2)

    poss_g1 = estimated_possessions(60, 20, 10, 10)  # TEAM_A game 1
    poss_g2 = estimated_possessions(58, 20, 8, 8)  # TEAM_A game 2
    opp_poss_g1 = estimated_possessions(45, 25, 15, 15)  # TEAM_B game 1
    opp_poss_g2 = estimated_possessions(55, 15, 12, 12)  # TEAM_C game 2
    expected_ortg = offensive_rating(80 + 90, poss_g1 + poss_g2)
    expected_drtg = defensive_rating(60 + 70, opp_poss_g1 + opp_poss_g2)

    assert overview["ortg"] == pytest.approx(round(expected_ortg, 1))
    assert overview["drtg"] == pytest.approx(round(expected_drtg, 1))
    assert overview["net_rating"] == pytest.approx(round(expected_ortg - expected_drtg, 1), abs=0.1)


def test_team_overview_excludes_games_without_box_score(db_session):
    db = db_session
    db.add(Competition(id="TEST_LEAGUE", name="Test League", season="2025-26"))
    db.add(Team(id="TEAM_A", competition_id="TEST_LEAGUE", name="Team A", short_name="A"))
    db.add(Team(id="TEAM_B", competition_id="TEST_LEAGUE", name="Team B", short_name="B"))
    # Game exists (e.g. schedule synced) but no PlayerGameStats rows at all yet.
    db.add(Game(id="G1", competition_id="TEST_LEAGUE", season="2025-26", round="1",
                game_date=datetime(2025, 10, 1), home_team_id="TEAM_A", away_team_id="TEAM_B",
                home_score=80, away_score=60, is_synced=True, raw_pbp_available=False))
    db.commit()

    overview = team_overview(db, "TEAM_A")
    assert overview["games_played"] == 0


def test_player_season_profile(two_game_season):
    profile = player_season_profile(two_game_season, "A1")
    assert profile["games_played"] == 2
    assert profile["ppg"] == pytest.approx((80 + 90) / 2)
    assert profile["rpg"] == pytest.approx((30 + 30) / 2)
    assert profile["apg"] == pytest.approx((20 + 18) / 2)
    assert profile["ts_pct"] == pytest.approx(true_shooting_pct(80 + 90, 60 + 58, 20 + 20), abs=1e-4)
    assert profile["ast_to"] == pytest.approx(assist_to_turnover(20 + 18, 10 + 8), abs=1e-2)
    assert len(profile["game_log"]) == 2
    assert profile["game_log"][0]["game_id"] == "G1"
    assert profile["game_log"][1]["game_id"] == "G2"
    assert len(profile["rolling_form"]) == 2
    # rolling window of 5 with only 2 games -> rolling_ppg after game 2 is the 2-game average
    assert profile["rolling_form"][1]["rolling_ppg"] == pytest.approx((80 + 90) / 2)


def test_player_season_profile_missing_player_returns_none(db_session):
    assert player_season_profile(db_session, "NOBODY") is None
