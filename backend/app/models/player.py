from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String(100))
    jersey_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    height_cm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    team: Mapped["Team"] = relationship(back_populates="players")
