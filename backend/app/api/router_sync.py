from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.sync import SyncStatusResponse, SyncTriggerResponse
from app.scrapers import sync_manager

router = APIRouter()


@router.post("/trigger", response_model=SyncTriggerResponse)
def trigger_sync(db: Session = Depends(get_db)):
    return sync_manager.trigger_sync(db)


@router.get("/status", response_model=SyncStatusResponse)
def sync_status(db: Session = Depends(get_db)):
    return sync_manager.get_sync_status(db)
