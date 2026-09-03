from app.mock_data import constants as C
from app.mock_data.generator import generate_mock_season
from app.models import Game, PlayByPlayEvent, PlayerGameStats, ShotEvent


def test_generate_mock_season_creates_expected_game_count(db_session):
    games_created = generate_mock_season(db_session)

    expected = 2 * len(C.WINNER_LEAGUE_OPPONENTS) + len(C.EUROCUP_OPPONENTS)
    assert games_created == expected
    assert db_session.query(Game).count() == expected


def test_generate_mock_season_is_idempotent(db_session):
    generate_mock_season(db_session)
    second_run = generate_mock_season(db_session)

    assert second_run == 0


def test_every_game_has_scores_and_synced_flags(db_session):
    generate_mock_season(db_session)

    for game in db_session.query(Game).all():
        assert game.home_score is not None
        assert game.away_score is not None
        assert game.home_score > 0
        assert game.away_score > 0
        assert game.is_synced is True
        assert game.raw_pbp_available is True
        assert game.home_score != game.away_score


def test_box_score_team_totals_match_player_sums(db_session):
    generate_mock_season(db_session)

    for game in db_session.query(Game).all():
        stats = db_session.query(PlayerGameStats).filter(PlayerGameStats.game_id == game.id).all()
        home_stats = [s for s in stats if s.team_id == game.home_team_id]
        away_stats = [s for s in stats if s.team_id == game.away_team_id]

        assert sum(s.points for s in home_stats) == game.home_score
        assert sum(s.points for s in away_stats) == game.away_score

        for team_stats in (home_stats, away_stats):
            for s in team_stats:
                assert s.fgm == s.fg2m + s.fg3m
                assert s.fga == s.fg2a + s.fg3a
                assert s.points == 2 * s.fg2m + 3 * s.fg3m + s.ftm
                assert s.reb == s.oreb + s.dreb
                assert s.fgm <= s.fga
                assert s.fg2m <= s.fg2a
                assert s.fg3m <= s.fg3a
                assert s.ftm <= s.fta


def test_shot_event_counts_match_box_score_field_goal_attempts(db_session):
    generate_mock_season(db_session)

    game = db_session.query(Game).first()
    stats = db_session.query(PlayerGameStats).filter(PlayerGameStats.game_id == game.id).all()
    shots = db_session.query(ShotEvent).filter(ShotEvent.game_id == game.id).all()

    total_fga = sum(s.fga for s in stats)
    total_fgm = sum(s.fgm for s in stats)
    assert len(shots) == total_fga
    assert sum(1 for sh in shots if sh.is_made) == total_fgm

    for player_id in {s.player_id for s in stats}:
        player_fga = sum(s.fga for s in stats if s.player_id == player_id)
        player_shots = [sh for sh in shots if sh.player_id == player_id]
        assert len(player_shots) == player_fga


def test_play_by_play_score_progression_ends_at_final_score(db_session):
    generate_mock_season(db_session)

    game = db_session.query(Game).first()
    events = (
        db_session.query(PlayByPlayEvent)
        .filter(PlayByPlayEvent.game_id == game.id)
        .order_by(PlayByPlayEvent.id)
        .all()
    )

    assert len(events) > 0
    last_event = events[-1]
    assert last_event.home_score == game.home_score
    assert last_event.away_score == game.away_score

    for event in events:
        assert len(event.current_lineup_home) == 5
        assert len(event.current_lineup_away) == 5
