from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    season: Mapped[str] = mapped_column(String(20))

    teams: Mapped[list["Team"]] = relationship(back_populates="competition")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    competition_id: Mapped[str] = mapped_column(ForeignKey("competitions.id"))
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(20))
    logo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary_team: Mapped[bool] = mapped_column(Boolean, default=False)

    competition: Mapped["Competition"] = relationship(back_populates="teams")
    players: Mapped[list["Player"]] = relationship(back_populates="team")
