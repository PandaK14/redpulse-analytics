"""One-off fix for a data-identity bug: 'Isaiah Mobley' (EuroCup source,
id EL_014206) and 'Isahiah Mobley' (Winner League source, id WL_1887) are
the same real person, but a single-letter name typo in the EuroCup feed
made both the exact-name and jersey-number dedup checks in
scrapers/common.py miss the match (fixed going forward with a fuzzy-name
fallback). Re-points every existing reference from the duplicate id to the
canonical one, then deletes the duplicate row.

Usage: python merge_duplicate_player.py <keep_id> <duplicate_id>
"""

import sys

from app.core.database import SessionLocal
from app.models import Player, PlayByPlayEvent, PlayerGameStats, ShotEvent


def merge(keep_id: str, dup_id: str) -> None:
    db = SessionLocal()
    keep = db.get(Player, keep_id)
    dup = db.get(Player, dup_id)
    if keep is None or dup is None:
        raise SystemExit(f"missing player row: keep={keep!r} dup={dup!r}")
    print(f"Merging {dup_id} ({dup.name!r}) into {keep_id} ({keep.name!r})")

    stats_moved = db.query(PlayerGameStats).filter_by(player_id=dup_id).update({"player_id": keep_id})

    pbp_primary = db.query(PlayByPlayEvent).filter_by(primary_player_id=dup_id).update({"primary_player_id": keep_id})
    pbp_secondary = db.query(PlayByPlayEvent).filter_by(secondary_player_id=dup_id).update({"secondary_player_id": keep_id})

    shot_player = db.query(ShotEvent).filter_by(player_id=dup_id).update({"player_id": keep_id})
    shot_assister = db.query(ShotEvent).filter_by(assister_id=dup_id).update({"assister_id": keep_id})

    lineup_rows_fixed = 0
    for event in db.query(PlayByPlayEvent).all():
        changed = False
        if dup_id in event.current_lineup_home:
            event.current_lineup_home = [keep_id if p == dup_id else p for p in event.current_lineup_home]
            changed = True
        if dup_id in event.current_lineup_away:
            event.current_lineup_away = [keep_id if p == dup_id else p for p in event.current_lineup_away]
            changed = True
        if changed:
            lineup_rows_fixed += 1

    db.delete(dup)
    db.commit()

    print(f"  player_game_stats moved: {stats_moved}")
    print(f"  pbp primary_player_id fixed: {pbp_primary}")
    print(f"  pbp secondary_player_id fixed: {pbp_secondary}")
    print(f"  shot_events player_id fixed: {shot_player}")
    print(f"  shot_events assister_id fixed: {shot_assister}")
    print(f"  lineup JSON arrays fixed: {lineup_rows_fixed}")
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    merge(sys.argv[1], sys.argv[2])
