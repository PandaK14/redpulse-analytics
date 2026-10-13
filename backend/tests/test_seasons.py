from datetime import date, datetime

import pytest

from app.models import Competition, Game, Player, PlayerGameStats, ShotEvent, Team
from app.scrapers.common import find_or_create_player
from app.services.seasons import current_season, list_seasons, resolve_season
from app.services.shot_chart import competition_average_shot_zones, team_shot_zones
from app.services.team_overview import team_overview, team_roster_with_averages

OLD, NEW = "2025-26", "2026-27"


def _game(db, game_id, season, home_pts, away_pts, when):
    db.add(
        Game(id=game_id, competition_id="LEAGUE", season=season, round="1", game_date=when,
             home_team_id="HAPOEL_JLM", away_team_id="OPP", home_score=home_pts, away_score=away_pts,
             is_synced=True, raw_pbp_available=False)
    )


def _stat(db, game_id, player_id, team_id, points):
    db.add(
        PlayerGameStats(id=f"{game_id}_{player_id}", game_id=game_id, player_id=player_id, team_id=team_id,
                        minutes_played=30, points=points, fgm=points // 2, fga=points // 2 + 2, fg2m=points // 2,
                        fg2a=points // 2 + 2, ftm=0, fta=0, reb=3, assists=2, turnovers=1)
    )


@pytest.fixture()
def two_seasons(db_session):
    db = db_session
    db.add(Competition(id="LEAGUE", name="League", season=NEW))
    db.add(Team(id="HAPOEL_JLM", competition_id="LEAGUE", name="Hapoel Jerusalem", short_name="HJ", is_primary_team=True))
    db.add(Team(id="OPP", competition_id="LEAGUE", name="Opponent", short_name="OPP"))
    db.add(Player(id="VETERAN", team_id="HAPOEL_JLM", name="Veteran Guard", jersey_number=1))
    db.add(Player(id="LEFT", team_id="HAPOEL_JLM", name="Left Wing", jersey_number=7))
    db.add(Player(id="OPP1", team_id="OPP", name="Opp One", jersey_number=9))
    db.flush()

    _game(db, "OLD1", OLD, 90, 80, datetime(2025, 11, 1))  # win
    _game(db, "OLD2", OLD, 70, 85, datetime(2025, 12, 1))  # loss
    _game(db, "NEW1", NEW, 100, 60, datetime(2026, 10, 5))  # win
    db.flush()
    # Results come from box-score points: OLD1 is a win (30-12), OLD2 a loss (30-50).
    for gid, opp_points in (("OLD1", 12), ("OLD2", 50)):
        _stat(db, gid, "VETERAN", "HAPOEL_JLM", 20)
        _stat(db, gid, "LEFT", "HAPOEL_JLM", 10)
        _stat(db, gid, "OPP1", "OPP", opp_points)
    _stat(db, "NEW1", "VETERAN", "HAPOEL_JLM", 30)
    _stat(db, "NEW1", "OPP1", "OPP", 8)
    db.commit()
    return db


def test_season_list_is_newest_first_and_marks_current(two_seasons):
    seasons = list_seasons(two_seasons)
    assert [s["id"] for s in seasons] == [NEW, OLD]
    assert [s["is_current"] for s in seasons] == [True, False]
    assert seasons[0]["label"] == "2026-2027"
    assert seasons[1]["games"] == 2


def test_resolve_season_defaults_to_latest(two_seasons):
    assert resolve_season(two_seasons, None) == NEW
    assert resolve_season(two_seasons, OLD) == OLD


def test_current_season_follows_the_calendar():
    assert current_season(date(2026, 10, 13)) == "2026-27"
    assert current_season(date(2026, 8, 1)) == "2026-27"
    assert current_season(date(2027, 5, 1)) == "2026-27"
    assert current_season(date(2026, 7, 31)) == "2025-26"


def test_team_overview_only_counts_the_requested_season(two_seasons):
    old = team_overview(two_seasons, "HAPOEL_JLM", season=OLD)
    new = team_overview(two_seasons, "HAPOEL_JLM", season=NEW)
    everything = team_overview(two_seasons, "HAPOEL_JLM")

    assert (old["wins"], old["losses"]) == (1, 1)
    assert (new["wins"], new["losses"]) == (1, 0)
    assert everything["games_played"] == 3


def test_roster_lists_only_players_who_played_that_season(two_seasons):
    old = {p["player_id"]: p for p in team_roster_with_averages(two_seasons, "HAPOEL_JLM", OLD)}
    new = {p["player_id"]: p for p in team_roster_with_averages(two_seasons, "HAPOEL_JLM", NEW)}

    assert set(old) == {"VETERAN", "LEFT"}
    assert set(new) == {"VETERAN"}
    assert old["VETERAN"]["ppg"] == 20.0
    assert new["VETERAN"]["ppg"] == 30.0
    assert new["VETERAN"]["games_played"] == 1


def test_shot_zones_are_scoped_by_season(two_seasons):
    db = two_seasons
    for i, (game_id, made) in enumerate([("OLD1", False), ("OLD2", False), ("NEW1", True)]):
        db.add(ShotEvent(id=f"S{i}", game_id=game_id, player_id="VETERAN", team_id="HAPOEL_JLM", period=1,
                         game_clock="09:00", x_coord=50, y_coord=2, shot_type="Rim", is_made=made))
    db.commit()

    def rim(zones):
        return next(z for z in zones if z["zone"] == "Rim")

    assert rim(team_shot_zones(db, "HAPOEL_JLM", "LEAGUE", OLD))["attempts"] == 2
    assert rim(team_shot_zones(db, "HAPOEL_JLM", "LEAGUE", NEW))["makes"] == 1
    assert rim(competition_average_shot_zones(db, "LEAGUE", NEW))["attempts"] == 1


class TestHapoelPlayerMatchingAcrossSeasons:
    def test_new_player_with_a_reused_jersey_is_not_merged_into_last_seasons_player(self, two_seasons):
        # LEFT wore #7 in 2025-26 and is not back; a newcomer wears #7 now.
        newcomer = find_or_create_player(two_seasons, "HAPOEL_JLM", "WL_NEW7", "New Seven", jersey=7, season=NEW)
        assert newcomer.id == "WL_NEW7"

    def test_jersey_still_bridges_sources_within_the_same_season(self, two_seasons):
        # A Hebrew-only box score row exists this season; the Latin-named feed
        # for the same game must resolve to it by jersey.
        two_seasons.add(Player(id="HEB", team_id="HAPOEL_JLM", name="שחקן", jersey_number=12))
        two_seasons.flush()
        _stat(two_seasons, "NEW1", "HEB", "HAPOEL_JLM", 5)
        two_seasons.flush()

        resolved = find_or_create_player(two_seasons, "HAPOEL_JLM", "EL_X", "Latin Name", jersey=12, season=NEW)
        assert resolved.id == "HEB"
        assert resolved.name == "Latin Name"

    def test_returning_player_keeps_one_row_and_gets_the_new_jersey(self, two_seasons):
        returning = find_or_create_player(two_seasons, "HAPOEL_JLM", "EL_NEW", "Veteran Guard", jersey=11, season=NEW)
        assert returning.id == "VETERAN"
        assert returning.jersey_number == 11

    def test_returning_player_with_a_misspelled_name_still_matches(self, two_seasons):
        returning = find_or_create_player(two_seasons, "HAPOEL_JLM", "EL_TYPO", "Veteran Guarrd", jersey=3, season=NEW)
        assert returning.id == "VETERAN"

    def test_different_name_is_not_fuzzy_matched(self, two_seasons):
        other = find_or_create_player(two_seasons, "HAPOEL_JLM", "EL_OTHER", "Vincent Gordon", jersey=3, season=NEW)
        assert other.id == "EL_OTHER"


def test_a_signing_from_another_club_joins_the_new_team_and_leaves_the_old_one(two_seasons):
    db = two_seasons
    # Filed under OPP (where he was first seen), but played for Hapoel in NEW.
    db.add(Player(id="SIGNING", team_id="OPP", name="Mid Season Signing", jersey_number=22))
    db.flush()
    _stat(db, "NEW1", "SIGNING", "HAPOEL_JLM", 14)
    db.commit()

    hapoel = {p["player_id"]: p for p in team_roster_with_averages(db, "HAPOEL_JLM", NEW)}
    opponent = {p["player_id"] for p in team_roster_with_averages(db, "OPP", NEW)}

    assert hapoel["SIGNING"]["ppg"] == 14.0
    assert "SIGNING" not in opponent
