"""Non-destructive sync of one season for both competitions. Run from backend/:
    .venv/bin/python sync_season.py 2026-27
Already-synced games are skipped, so it is safe to re-run as games get played."""

import sys
import time

from app.core.database import SessionLocal
from app.scrapers.eurocup_scraper import EuroCupScraper
from app.scrapers.winner_league_scraper import WinnerLeagueScraper
from app.services.seasons import end_year_for_season, euroleague_code_for_season


def main(season: str) -> None:
    db = SessionLocal()
    start = time.time()
    wl = WinnerLeagueScraper().sync(db, cyear=end_year_for_season(season))
    print(f"Winner League {season}: {wl} new games ({time.time() - start:.0f}s)", flush=True)
    ec = EuroCupScraper().sync(db, season_code=euroleague_code_for_season(season))
    print(f"EuroCup {season}: {ec} new games ({time.time() - start:.0f}s)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
