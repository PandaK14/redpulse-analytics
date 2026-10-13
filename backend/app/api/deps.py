from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.seasons import resolve_season


def get_season(
    season: Optional[str] = Query(None, description='Season id such as "2025-26"; defaults to the latest synced season'),
    db: Session = Depends(get_db),
) -> Optional[str]:
    return resolve_season(db, season)
