from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 register model metadata before create_all
from app.api.router_player import router as player_router
from app.api.router_sync import router as sync_router
from app.api.router_team import router as team_router
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="RedPulse Analytics API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
