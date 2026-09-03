from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.mock_data.generator import generate_mock_season
from app.models import Game
from app.scrapers.eurocup_scraper import EuroCupScraper
from app.scrapers.winner_league_scraper import WinnerLeagueScraper
from app.services.team_overview import invalidate_league_average_cache

# Process-local sync bookkeeping. Good enough for a single dev/API process;
# a persisted sync_log table would be the natural upgrade once this runs
# behind multiple workers.
_last_sync_at: Optional[datetime] = None
_last_sync_status: str = "never_run"
_last_sync_source: str = "none"


def trigger_sync(db: Session) -> dict:
    global _last_sync_at, _last_sync_status, _last_sync_source
    settings = get_settings()

    if settings.use_mock_data:
        games_synced = generate_mock_season(db)
        source = "mock_data_generator"
        errors: list[str] = []
    else:
        games_synced, errors = _sync_live_sources(db, settings)
        source = "live_scrapers"

    if games_synced:
        invalidate_league_average_cache()

    _last_sync_at = datetime.now(timezone.utc)
    _last_sync_status = "success" if not errors else "partial_failure"
    _last_sync_source = source

    if errors:
        message = f"Synced {games_synced} new games via {source}, with errors: {'; '.join(errors)}"
    elif games_synced:
        message = f"Synced {games_synced} new games via {source}."
    else:
        message = f"No new games to sync via {source} (already up to date)."

    return {"status": _last_sync_status, "games_synced": games_synced, "source": source, "message": message}


def _sync_live_sources(db: Session, settings) -> tuple[int, list[str]]:
    games_synced = 0
    errors = []

    try:
        winner_league_count = WinnerLeagueScraper().sync(
            db, cyear=settings.winner_league_cyear, max_games=settings.scraper_max_games
        )
        db.commit()
        games_synced += winner_league_count
    except httpx.HTTPError as exc:
        db.rollback()
        errors.append(f"Winner League scrape failed: {exc}")

    try:
        eurocup_count = EuroCupScraper().sync(
            db, season_code=settings.eurocup_season_code, max_games=settings.scraper_max_games
        )
        db.commit()
        games_synced += eurocup_count
    except httpx.HTTPError as exc:
        db.rollback()
        errors.append(f"EuroCup scrape failed: {exc}")

    return games_synced, errors


def get_sync_status(db: Session) -> dict:
    return {
        "last_sync_at": _last_sync_at,
        "last_sync_status": _last_sync_status,
        "last_sync_source": _last_sync_source,
        "games_in_db": db.query(Game).count(),
    }
