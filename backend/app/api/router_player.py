from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import PlayerProfile, ShotZoneStat
from app.services.advanced_stats import player_season_profile
from app.services.shot_chart import player_shot_zones

router = APIRouter()


@router.get("/{player_id}", response_model=PlayerProfile)
def get_player_profile(player_id: str, db: Session = Depends(get_db)):
    profile = player_season_profile(db, player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Player not found or has no synced games")
    return profile


@router.get("/{player_id}/shots", response_model=list[ShotZoneStat])
def get_player_shots(player_id: str, db: Session = Depends(get_db)):
    return player_shot_zones(db, player_id)
