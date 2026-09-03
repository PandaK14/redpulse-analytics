"""Shot zone aggregation over ShotEvent rows. Zone names match exactly what
the scrapers write (see winner_league_scraper._classify_shot_zone and
eurocup_scraper._classify_shot_zone)."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, ShotEvent

ZONES = ["Rim", "Paint", "Mid-Range", "Corner-3", "Above-the-Break-3"]
THREE_POINT_ZONES = {"Corner-3", "Above-the-Break-3"}


def _zone_stats(shots: list[ShotEvent]) -> list[dict]:
    total_attempts = len(shots)
    result = []
    for zone in ZONES:
        zone_shots = [s for s in shots if s.shot_type == zone]
        attempts = len(zone_shots)
        makes = sum(1 for s in zone_shots if s.is_made)
        points_value = 3 if zone in THREE_POINT_ZONES else 2
        result.append(
            {
                "zone": zone,
                "attempts": attempts,
                "makes": makes,
                "fg_pct": round(makes / attempts, 4) if attempts else 0.0,
                "volume_pct": round(attempts / total_attempts, 4) if total_attempts else 0.0,
                "points_per_shot": round((makes * points_value) / attempts, 3) if attempts else 0.0,
            }
        )
    return result


def team_shot_zones(db: Session, team_id: str, competition_id: Optional[str] = None) -> list[dict]:
    query = db.query(ShotEvent).filter(ShotEvent.team_id == team_id)
    if competition_id and competition_id != "ALL":
        query = query.join(Game, Game.id == ShotEvent.game_id).filter(Game.competition_id == competition_id)
    return _zone_stats(query.all())


def player_shot_zones(db: Session, player_id: str) -> list[dict]:
    shots = db.query(ShotEvent).filter(ShotEvent.player_id == player_id).all()
    return _zone_stats(shots)


def competition_average_shot_zones(db: Session, competition_id: str) -> list[dict]:
    shots = (
        db.query(ShotEvent)
        .join(Game, Game.id == ShotEvent.game_id)
        .filter(Game.competition_id == competition_id)
        .all()
    )
    return _zone_stats(shots)
