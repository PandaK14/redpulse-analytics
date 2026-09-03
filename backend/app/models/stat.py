from typing import Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))

    minutes_played: Mapped[float] = mapped_column(Numeric(5, 2))
    points: Mapped[int] = mapped_column(Integer, default=0)
    fgm: Mapped[int] = mapped_column(Integer, default=0)
    fga: Mapped[int] = mapped_column(Integer, default=0)
    fg2m: Mapped[int] = mapped_column(Integer, default=0)
    fg2a: Mapped[int] = mapped_column(Integer, default=0)
    fg3m: Mapped[int] = mapped_column(Integer, default=0)
    fg3a: Mapped[int] = mapped_column(Integer, default=0)
    ftm: Mapped[int] = mapped_column(Integer, default=0)
    fta: Mapped[int] = mapped_column(Integer, default=0)
    oreb: Mapped[int] = mapped_column(Integer, default=0)
    dreb: Mapped[int] = mapped_column(Integer, default=0)
    reb: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    steals: Mapped[int] = mapped_column(Integer, default=0)
    turnovers: Mapped[int] = mapped_column(Integer, default=0)
    blocks: Mapped[int] = mapped_column(Integer, default=0)
    personal_fouls: Mapped[int] = mapped_column(Integer, default=0)
    fouls_drawn: Mapped[int] = mapped_column(Integer, default=0)
    plus_minus: Mapped[int] = mapped_column(Integer, default=0)
    valuation: Mapped[int] = mapped_column(Integer, default=0)


class PlayByPlayEvent(Base):
    __tablename__ = "play_by_play_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    period: Mapped[int] = mapped_column(Integer)
    game_clock: Mapped[str] = mapped_column(String(10))
    event_type: Mapped[str] = mapped_column(String(50))
    acting_team_id: Mapped[Optional[str]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    primary_player_id: Mapped[Optional[str]] = mapped_column(ForeignKey("players.id"), nullable=True)
    secondary_player_id: Mapped[Optional[str]] = mapped_column(ForeignKey("players.id"), nullable=True)
    home_score: Mapped[int] = mapped_column(Integer)
    away_score: Mapped[int] = mapped_column(Integer)
    # Stored as JSON arrays (portable across SQLite dev / Postgres prod) rather than
    # Postgres-only ARRAY, matching the TEXT[] intent in the PRD schema.
    current_lineup_home: Mapped[list[str]] = mapped_column(JSON)
    current_lineup_away: Mapped[list[str]] = mapped_column(JSON)


class ShotEvent(Base):
    __tablename__ = "shot_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    period: Mapped[int] = mapped_column(Integer)
    game_clock: Mapped[str] = mapped_column(String(10))
    x_coord: Mapped[float] = mapped_column(Numeric(5, 2))
    y_coord: Mapped[float] = mapped_column(Numeric(5, 2))
    shot_type: Mapped[str] = mapped_column(String(50))
    is_made: Mapped[bool] = mapped_column(Boolean)
    is_assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    assister_id: Mapped[Optional[str]] = mapped_column(ForeignKey("players.id"), nullable=True)
