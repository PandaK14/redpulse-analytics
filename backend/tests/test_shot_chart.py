from datetime import datetime

import pytest

from app.models import Competition, Game, Player, ShotEvent, Team
from app.services.shot_chart import competition_average_shot_zones, player_shot_zones, team_shot_zones


@pytest.fixture()
def shot_fixture(db_session):
    db = db_session
    db.add(Competition(id="TEST_LEAGUE", name="Test League", season="2025-26"))
    db.add(Team(id="TEAM_A", competition_id="TEST_LEAGUE", name="Team A", short_name="A"))
    db.add(Team(id="TEAM_B", competition_id="TEST_LEAGUE", name="Team B", short_name="B"))
    db.add(Player(id="A1", team_id="TEAM_A", name="Player A1", jersey_number=1))
    db.add(Game(id="G1", competition_id="TEST_LEAGUE", season="2025-26", round="1",
                game_date=datetime(2025, 10, 1), home_team_id="TEAM_A", away_team_id="TEAM_B",
                home_score=50, away_score=40, is_synced=True, raw_pbp_available=True))
    db.flush()

    # TEAM_A / Player A1: 4 Rim attempts (3 made), 4 Above-the-Break-3 attempts (1 made)
    shots = []
    for i in range(4):
        shots.append(ShotEvent(id=f"RIM_{i}", game_id="G1", player_id="A1", team_id="TEAM_A", period=1,
                                game_clock="09:00", x_coord=50, y_coord=2, shot_type="Rim",
                                is_made=(i < 3), is_assisted=False))
    for i in range(4):
        shots.append(ShotEvent(id=f"AB3_{i}", game_id="G1", player_id="A1", team_id="TEAM_A", period=1,
                                game_clock="08:00", x_coord=50, y_coord=25, shot_type="Above-the-Break-3",
                                is_made=(i < 1), is_assisted=False))
    db.add_all(shots)
    db.commit()
    return db


def test_zone_stats_math(shot_fixture):
    zones = {z["zone"]: z for z in team_shot_zones(shot_fixture, "TEAM_A")}

    rim = zones["Rim"]
    assert rim["attempts"] == 4
    assert rim["makes"] == 3
    assert rim["fg_pct"] == pytest.approx(0.75)
    assert rim["volume_pct"] == pytest.approx(4 / 8)  # 4 of 8 total attempts
    assert rim["points_per_shot"] == pytest.approx(2 * 3 / 4)  # 2 points/make, 3 makes, 4 attempts

    three = zones["Above-the-Break-3"]
    assert three["attempts"] == 4
    assert three["makes"] == 1
    assert three["fg_pct"] == pytest.approx(0.25)
    assert three["volume_pct"] == pytest.approx(4 / 8)
    assert three["points_per_shot"] == pytest.approx(3 * 1 / 4)  # 3 points/make, 1 make, 4 attempts

    # Zones with no attempts should report zero, not error
    assert zones["Paint"]["attempts"] == 0
    assert zones["Paint"]["fg_pct"] == 0.0
    assert zones["Paint"]["volume_pct"] == 0.0


def test_player_shot_zones_matches_team_when_solo_scorer(shot_fixture):
    # Player A1 is the only shooter on TEAM_A in this fixture, so the two should agree.
    assert player_shot_zones(shot_fixture, "A1") == team_shot_zones(shot_fixture, "TEAM_A")


def test_empty_shot_zones_do_not_error(db_session):
    db_session.add(Competition(id="EMPTY_LEAGUE", name="Empty League", season="2025-26"))
    db_session.commit()
    zones = competition_average_shot_zones(db_session, "EMPTY_LEAGUE")
    assert len(zones) == 5
    assert all(z["attempts"] == 0 for z in zones)
