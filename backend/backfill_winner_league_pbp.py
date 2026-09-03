"""One-off backfill: re-sync play-by-play + shot events for every Winner
League game with a segevstats link. Needed because the original
_sync_play_by_play only added points to the running score on made field
goals, never on made free throws — every game's PBP score progression
(and hence lineup-derived ratings) undercounted by however many points a
team scored at the line. Box scores are untouched and correct; this only
replaces PlayByPlayEvent/ShotEvent rows for games that already have PBP.

Run from backend/ with the venv active: python backfill_winner_league_pbp.py
"""

import time

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Game, PlayByPlayEvent, ShotEvent
from app.scrapers.winner_league_scraper import WinnerLeagueScraper

DB_PATH = "sqlite:///./redpulse.db"
DELAY = 0.4


def main():
    engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    scraper = WinnerLeagueScraper()
    game_ids = [
        row[0]
        for row in db.query(Game.id)
        .filter(Game.competition_id == "WINNER_LEAGUE", Game.raw_pbp_available.is_(True))
        .all()
    ]
    print(f"Re-syncing PBP for {len(game_ids)} Winner League games", flush=True)

    fixed = 0
    failed = []
    for i, game_id in enumerate(game_ids, start=1):
        game = db.get(Game, game_id)
        game_zone_id = game_id.replace("WL_", "")

        try:
            segev_id = scraper.find_segev_game_id(game_zone_id)
            if not segev_id:
                failed.append(game_id)
                continue
            box_score = scraper.fetch_box_score(game_zone_id)
            home_rows = box_score.get(game.home_team_id, []) if box_score else []
            away_rows = box_score.get(game.away_team_id, []) if box_score else []
            home_starters = {r["jersey"] for r in home_rows if r["starter"] == "*"}
            away_starters = {r["jersey"] for r in away_rows if r["starter"] == "*"}

            db.execute(delete(PlayByPlayEvent).where(PlayByPlayEvent.game_id == game_id))
            db.execute(delete(ShotEvent).where(ShotEvent.game_id == game_id))
            scraper._sync_play_by_play(db, game, game.home_team_id, game.away_team_id, segev_id, home_starters, away_starters)
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
