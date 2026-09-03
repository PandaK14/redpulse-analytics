from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SyncTriggerResponse(BaseModel):
    status: str
    games_synced: int
    source: str
    message: str


class SyncStatusResponse(BaseModel):
    last_sync_at: Optional[datetime]
    last_sync_status: str
    last_sync_source: str
    games_in_db: int
