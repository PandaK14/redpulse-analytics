from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    competition_id: Mapped[str] = mapped_column(ForeignKey("competitions.id"))
    season: Mapped[str] = mapped_column(String(20))
    round: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    game_date: Mapped[datetime] = mapped_column(DateTime)
    home_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_pbp_available: Mapped[bool] = mapped_column(Boolean, default=False)
