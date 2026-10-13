from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import SeasonInfo
from app.services.seasons import list_seasons

router = APIRouter()


@router.get("", response_model=list[SeasonInfo])
def get_seasons(db: Session = Depends(get_db)):
    return list_seasons(db)
