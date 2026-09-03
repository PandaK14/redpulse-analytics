"""Hand-traced stint reconstruction: TEAM_A (home) plays one lineup for the
first part of the game, subs P5 -> P6, and plays a second lineup for the
rest. Expected minutes/points/ratings below are computed independently in
the comments so this test actually catches a wrong formula, not just a
"changed since last run" regression.

Game clock: period 1, FIBA 10-minute quarter (600s), counting down.
    elapsed_seconds(clock) = 600 - (mm*60 + ss)

Event log (TEAM_A=home, TEAM_B=away):
    1. 09:50  SHOT   TEAM_A P1  MADE 2pt   -> home 2-0        elapsed=10
    2. 09:30  SHOT   TEAM_B Q1  MISS                          elapsed=30
    3. 09:20  REBOUND TEAM_A P2 (defensive: last shot was TEAM_B's miss)
    4. 09:00  TURNOVER TEAM_A P3                              elapsed=60
    5. 08:40  SHOT   TEAM_B Q2  MADE 3pt   -> away 2-3        elapsed=80
    --- substitution: P5 out, P6 in for TEAM_A ---
    6. 08:00  SHOT   TEAM_A P1  MADE 2pt   -> home 4-3        elapsed=120  (stint boundary)
    7. 07:40  SHOT   TEAM_B Q3  MISS                          elapsed=140
    8. 07:20  FREE_THROW TEAM_A P2 MADE 1pt -> home 5-3       elapsed=160

Stint 1 (lineup P1-P5), elapsed 10 -> 120 (110s = 1.8333 min):
    team:  fga=1 (ev1), tov=1 (ev4)              -> poss = 1 + 0 - 0 + 1 = 2
    opp:   fga=2 (ev2, ev5)                       -> poss = 2 + 0 - 0 + 0 = 2
    team_points=2, opp_points=3
    ORtg = 100*2/2 = 100.0   DRtg = 100*3/2 = 150.0   Net = -50.0   +/- = -1

Stint 2 (lineup P1-P4,P6), elapsed 120 -> 160 (40s = 0.6667 min):
    team:  fga=1 (ev6), fta=1 (ev8)               -> poss = 1 + 0.44 - 0 + 0 = 1.44
    opp:   fga=1 (ev7)                             -> poss = 1
    team_points=3 (ev6 +2, ev8 +1), opp_points=0
    ORtg = 100*3/1.44 = 208.33   DRtg = 0.0   Net = 208.33   +/- = 3
"""

from datetime import datetime

import pytest

from app.models import Competition, Game, Player, PlayByPlayEvent, Team
from app.services.lineups import lineup_table, on_off_table

P1, P2, P3, P4, P5, P6 = "P1", "P2", "P3", "P4", "P5", "P6"
Q1, Q2, Q3, Q4, Q5 = "Q1", "Q2", "Q3", "Q4", "Q5"
LINEUP_1 = [P1, P2, P3, P4, P5]
LINEUP_2 = [P1, P2, P3, P4, P6]
AWAY_LINEUP = [Q1, Q2, Q3, Q4, Q5]


@pytest.fixture()
def lineup_game(db_session):
    db = db_session
    db.add(Competition(id="TEST_LEAGUE", name="Test League", season="2025-26"))
    db.add(Team(id="TEAM_A", competition_id="TEST_LEAGUE", name="Team A", short_name="A"))
    db.add(Team(id="TEAM_B", competition_id="TEST_LEAGUE", name="Team B", short_name="B"))
    for pid in [P1, P2, P3, P4, P5, P6]:
        db.add(Player(id=pid, team_id="TEAM_A", name=pid))
    for pid in [Q1, Q2, Q3, Q4, Q5]:
        db.add(Player(id=pid, team_id="TEAM_B", name=pid))
    db.add(Game(id="G1", competition_id="TEST_LEAGUE", season="2025-26", round="1",
                game_date=datetime(2025, 10, 1), home_team_id="TEAM_A", away_team_id="TEAM_B",
                home_score=5, away_score=3, is_synced=True, raw_pbp_available=True))
    db.flush()

    events = [
        dict(id="E1", period=1, game_clock="09:50", event_type="SHOT", acting_team_id="TEAM_A",
             primary_player_id=P1, home_score=2, away_score=0, lineup=LINEUP_1),
        dict(id="E2", period=1, game_clock="09:30", event_type="SHOT", acting_team_id="TEAM_B",
             primary_player_id=Q1, home_score=2, away_score=0, lineup=LINEUP_1),
        dict(id="E3", period=1, game_clock="09:20", event_type="REBOUND", acting_team_id="TEAM_A",
             primary_player_id=P2, home_score=2, away_score=0, lineup=LINEUP_1),
        dict(id="E4", period=1, game_clock="09:00", event_type="TURNOVER", acting_team_id="TEAM_A",
             primary_player_id=P3, home_score=2, away_score=0, lineup=LINEUP_1),
        dict(id="E5", period=1, game_clock="08:40", event_type="SHOT", acting_team_id="TEAM_B",
             primary_player_id=Q2, home_score=2, away_score=3, lineup=LINEUP_1),
        dict(id="E6", period=1, game_clock="08:00", event_type="SHOT", acting_team_id="TEAM_A",
             primary_player_id=P1, home_score=4, away_score=3, lineup=LINEUP_2),
        dict(id="E7", period=1, game_clock="07:40", event_type="SHOT", acting_team_id="TEAM_B",
             primary_player_id=Q3, home_score=4, away_score=3, lineup=LINEUP_2),
        dict(id="E8", period=1, game_clock="07:20", event_type="FREE_THROW", acting_team_id="TEAM_A",
             primary_player_id=P2, home_score=5, away_score=3, lineup=LINEUP_2),
    ]
    for e in events:
        db.add(
            PlayByPlayEvent(
                id=e["id"], game_id="G1", period=e["period"], game_clock=e["game_clock"],
                event_type=e["event_type"], acting_team_id=e["acting_team_id"],
                primary_player_id=e["primary_player_id"], secondary_player_id=None,
                home_score=e["home_score"], away_score=e["away_score"],
                current_lineup_home=e["lineup"], current_lineup_away=AWAY_LINEUP,
            )
        )
    db.commit()
    return db


def _find(rows, player_ids):
    key = set(player_ids)
    for r in rows:
        if set(r["player_ids"]) == key:
            return r
    raise AssertionError(f"no row found for {player_ids} in {rows}")


def test_five_man_lineup_table(lineup_game):
    rows = lineup_table(lineup_game, "TEAM_A", size=5)
    assert len(rows) == 2

    stint1 = _find(rows, LINEUP_1)
    assert stint1["minutes"] == pytest.approx(110 / 60, abs=0.05)
    assert stint1["possessions"] == pytest.approx(2.0, abs=0.05)
    assert stint1["ortg"] == pytest.approx(100.0, abs=0.1)
    assert stint1["drtg"] == pytest.approx(150.0, abs=0.1)
    assert stint1["net_rating"] == pytest.approx(-50.0, abs=0.1)
    assert stint1["plus_minus"] == -1

    stint2 = _find(rows, LINEUP_2)
    assert stint2["minutes"] == pytest.approx(40 / 60, abs=0.05)
    assert stint2["possessions"] == pytest.approx(1.44, abs=0.05)
    assert stint2["ortg"] == pytest.approx(208.33, abs=0.1)
    assert stint2["drtg"] == pytest.approx(0.0, abs=0.01)
    assert stint2["net_rating"] == pytest.approx(208.33, abs=0.1)
    assert stint2["plus_minus"] == 3


def test_min_minutes_filter(lineup_game):
    rows = lineup_table(lineup_game, "TEAM_A", size=5, min_minutes=1.0)
    assert len(rows) == 1
    assert set(rows[0]["player_ids"]) == set(LINEUP_1)


def test_three_man_combo_spans_both_stints(lineup_game):
    # P1, P2, P3 are common to both 5-man lineups, so their 3-man combo
    # should be credited with the full game's minutes (both stints).
    rows = lineup_table(lineup_game, "TEAM_A", size=3)
    combo = _find(rows, [P1, P2, P3])
    assert combo["minutes"] == pytest.approx(150 / 60, abs=0.01)  # 110s + 40s


def test_on_off_table(lineup_game):
    rows = {r["player_id"]: r for r in on_off_table(lineup_game, "TEAM_A")}

    # P5 played only stint 1, P6 only stint 2 — mirror images of each other.
    p5, p6 = rows["P5"], rows["P6"]
    assert p5["minutes_on"] == pytest.approx(110 / 60, abs=0.05)
    assert p5["minutes_off"] == pytest.approx(40 / 60, abs=0.05)
    assert p5["net_rating_on"] == pytest.approx(-50.0, abs=0.1)
    assert p5["net_rating_off"] == pytest.approx(208.33, abs=0.1)
    assert p5["on_off_diff"] == pytest.approx(-258.33, abs=0.2)

    assert p6["minutes_on"] == pytest.approx(40 / 60, abs=0.05)
    assert p6["minutes_off"] == pytest.approx(110 / 60, abs=0.05)
    assert p6["on_off_diff"] == pytest.approx(258.33, abs=0.2)

    # P1 played every second of the game -> no "off" minutes -> diff is None.
    p1 = rows["P1"]
    assert p1["minutes_off"] == 0
    assert p1["on_off_diff"] is None
