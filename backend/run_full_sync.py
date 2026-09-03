"""One-off script: wipe the dev DB and run a full real-data sync for both
competitions (no max_games cap). Run from backend/ with the venv active:
    python run_full_sync.py
"""

import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 register model metadata
from app.core.database import Base
from app.scrapers.eurocup_scraper import EuroCupScraper
from app.scrapers.winner_league_scraper import WinnerLeagueScraper

DB_PATH = "sqlite:///./redpulse.db"


def main():
    engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    start = time.time()
    print("=== Winner League sync starting ===", flush=True)
    wl_count = WinnerLeagueScraper().sync(db, cyear=2026, max_games=None, delay=0.4)
    print(f"Winner League: {wl_count} games synced ({time.time() - start:.0f}s elapsed)", flush=True)

    start2 = time.time()
    print("=== EuroCup sync starting ===", flush=True)
    ec_count = EuroCupScraper().sync(db, season_code="U2025", max_games=None, delay=0.4)
    print(f"EuroCup: {ec_count} games synced ({time.time() - start2:.0f}s elapsed)", flush=True)

    print(f"=== DONE: {wl_count + ec_count} total games, {time.time() - start:.0f}s total ===", flush=True)


if __name__ == "__main__":
    main()
