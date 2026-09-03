"""One-off backfill: re-sync play-by-play + shot events for every EuroCup
game. Needed because the original _sync_play_by_play trusted the live feed's
POINTS_A/POINTS_B as a running score, but the feed only populates them on
the scoring play itself (null otherwise) — the fixed scraper now carries the
last known value forward. Box scores are untouched and correct; this only
replaces PlayByPlayEvent/ShotEvent rows.

Run from backend/ with the venv active: python backfill_eurocup_pbp.py
"""

import time

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Game, PlayByPlayEvent, ShotEvent
from app.scrapers.eurocup_scraper import EuroCupScraper

DB_PATH = "sqlite:///./redpulse.db"
SEASON_CODE = "U2025"
DELAY = 0.5


def main():
    engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    scraper = EuroCupScraper()
    schedule = {f"EL_{SEASON_CODE}_{g['gameCode']}": g for g in scraper.fetch_schedule(SEASON_CODE)}

    game_ids = [row[0] for row in db.query(Game.id).filter(Game.competition_id == "EUROCUP").all()]
    print(f"Re-syncing PBP for {len(game_ids)} EuroCup games", flush=True)

    fixed = 0
    failed = []
    for i, game_id in enumerate(game_ids, start=1):
        g = schedule.get(game_id)
        game = db.get(Game, game_id)
        if g is None or game is None:
            failed.append(game_id)
            continue

        try:
            db.execute(delete(PlayByPlayEvent).where(PlayByPlayEvent.game_id == game_id))
            db.execute(delete(ShotEvent).where(ShotEvent.game_id == game_id))
            home_team_id = scraper._team_id_for(g["home_code"])
            away_team_id = scraper._team_id_for(g["away_code"])
            box_score = scraper._fetch_box_score(SEASON_CODE, g["gameCode"])
            scraper._sync_play_by_play(
                db, game, home_team_id, away_team_id,
                g["home_code"], g["away_code"], SEASON_CODE, g["gameCode"], box_score,
            )
            game.raw_pbp_available = True
            db.commit()
            fixed += 1
        except Exception as exc:
            db.rollback()
            game.raw_pbp_available = False
            db.commit()
            print(f"  [{i}/{len(game_ids)}] {game_id} failed: {exc}", flush=True)
            failed.append(game_id)

        if i % 20 == 0:
            print(f"  [{i}/{len(game_ids)}] fixed so far: {fixed}", flush=True)
        time.sleep(DELAY)

    print(f"=== DONE: fixed {fixed}, failed {len(failed)} ===", flush=True)
    if failed:
        print("Failed:", failed, flush=True)


if __name__ == "__main__":
    main()
