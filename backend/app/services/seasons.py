"""Season helpers. A season id is the label stored on Game.season, e.g.
"2025-26" (basket.co.il cYear 2026 / Euroleague code U2025)."""

from datetime import date
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Game


def season_id_for_end_year(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def end_year_for_season(season: str) -> int:
    return int(season[:4]) + 1


def euroleague_code_for_season(season: str) -> str:
    return f"U{season[:4]}"


def season_label(season: str) -> str:
    start = int(season[:4])
    return f"{start}-{start + 1}"


def list_seasons(db: Session) -> list[dict]:
    rows = (
        db.query(Game.season, func.count(Game.id))
        .filter(Game.is_synced.is_(True))
        .group_by(Game.season)
        .order_by(Game.season.desc())
        .all()
    )
    return [
        {"id": season, "label": season_label(season), "games": count, "is_current": index == 0}
        for index, (season, count) in enumerate(rows)
    ]


def resolve_season(db: Session, season: Optional[str]) -> Optional[str]:
    """The requested season, or the most recent one that has synced games."""
    if season:
        return season
    latest = (
        db.query(Game.season).filter(Game.is_synced.is_(True)).order_by(Game.season.desc()).limit(1).scalar()
    )
    return latest


def current_season(today: Optional[date] = None) -> str:
    """The season in progress by the calendar: both leagues tip off in
    September/October, so August onward belongs to the new season."""
    today = today or date.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    return season_id_for_end_year(start_year + 1)
