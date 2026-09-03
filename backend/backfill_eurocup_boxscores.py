"""One-off backfill: retry box score + PBP for EuroCup games that already
have a Game row (so a normal sync() call would skip them as "already
synced") but ended up with zero PlayerGameStats rows, most likely due to
api-live.euroleague.net rate-limiting during the full-season sync.

Run from backend/ with the venv active: python backfill_eurocup_boxscores.py
"""

import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Game
from app.scrapers.eurocup_scraper import EuroCupScraper

DB_PATH = "sqlite:///./redpulse.db"
SEASON_CODE = "U2025"
DELAY = 1.5  # more conservative than the normal 0.4s to stay under the rate limit


def main():
    engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    missing_ids = [
        row[0]
        for row in db.execute(
            text(
                "SELECT g.id FROM games g WHERE g.competition_id = 'EUROCUP' "
                "AND NOT EXISTS (SELECT 1 FROM player_game_stats WHERE game_id = g.id)"
            )
        ).fetchall()
    ]
    print(f"Found {len(missing_ids)} EuroCup games missing box scores", flush=True)

    scraper = EuroCupScraper()
    schedule = {f"EL_{SEASON_CODE}_{g['gameCode']}": g for g in scraper.fetch_schedule(SEASON_CODE)}

    filled = 0
    still_missing = []
    for i, game_id in enumerate(missing_ids, start=1):
        g = schedule.get(game_id)
        game = db.get(Game, game_id)
        if g is None or game is None:
            still_missing.append(game_id)
            continue

        try:
            home_team_id = scraper._team_id_for(g["home_code"])
            away_team_id = scraper._team_id_for(g["away_code"])
            box_score = scraper._fetch_box_score(SEASON_CODE, g["gameCode"])
            if box_score:
                scraper._persist_box_score(db, game, home_team_id, box_score["local"]["players"])
                scraper._persist_box_score(db, game, away_team_id, box_score["road"]["players"])
                try:
                    scraper._sync_play_by_play(
                        db, game, home_team_id, away_team_id,
                        g["home_code"], g["away_code"], SEASON_CODE, g["gameCode"],
                    )
                    game.raw_pbp_available = True
                except Exception:
                    pass
                db.commit()
                filled += 1
            else:
                still_missing.append(game_id)
        except Exception as exc:
            db.rollback()
            print(f"  [{i}/{len(missing_ids)}] {game_id} failed: {exc}", flush=True)
            still_missing.append(game_id)

        if i % 20 == 0:
            print(f"  [{i}/{len(missing_ids)}] filled so far: {filled}", flush=True)
        time.sleep(DELAY)

    print(f"=== DONE: filled {filled}, still missing {len(still_missing)} ===", flush=True)
    if still_missing:
        print("Still missing:", still_missing, flush=True)


if __name__ == "__main__":
    main()
