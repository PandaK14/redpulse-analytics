import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 register model metadata before create_all
from app.api.router_player import router as player_router
from app.api.router_sync import router as sync_router
from app.api.router_team import router as team_router
from app.core.database import Base, engine

# On a fresh deploy (e.g. Render's ephemeral filesystem after a cold start),
# there's no synced data yet. Rather than serve an empty demo, seed from a
# committed snapshot of real, already-synced data if the live db is missing.
BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_DB_PATH = BACKEND_DIR / "data" / "seed_redpulse.db"
LIVE_DB_PATH = BACKEND_DIR / "redpulse.db"


def _seed_database_if_missing() -> None:
    if not LIVE_DB_PATH.exists() and SEED_DB_PATH.exists():
        shutil.copyfile(SEED_DB_PATH, LIVE_DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_database_if_missing()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="RedPulse Analytics API", lifespan=lifespan)

# CORS_ORIGINS is a comma-separated list (e.g. the deployed Vercel URL);
# defaults to local dev only.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sync_router, prefix="/api/sync", tags=["sync"])
app.include_router(team_router, prefix="/api/teams", tags=["teams"])
app.include_router(player_router, prefix="/api/players", tags=["players"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
