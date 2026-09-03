from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Team
from app.services import team_overview as svc

router = APIRouter()


@router.get("/{team_id}/overview")
def get_team_overview(team_id: str, competition: Optional[str] = "ALL", db: Session = Depends(get_db)):
    overview = svc.team_overview(db, team_id, competition)
    overview["league_avg_four_factors"] = svc.competition_average_four_factors(db, "WINNER_LEAGUE")
    overview["eurocup_avg_four_factors"] = svc.competition_average_four_factors(db, "EUROCUP")
    return overview


@router.get("/{team_id}/roster")
def get_team_roster(team_id: str, db: Session = Depends(get_db)):
    return svc.team_roster_with_averages(db, team_id)


@router.get("/{team_id}/games")
def get_team_games(team_id: str, db: Session = Depends(get_db)):
    return svc.team_games(db, team_id)


@router.get("")
def list_teams(db: Session = Depends(get_db)):
    return [
        {"id": t.id, "name": t.name, "short_name": t.short_name, "competition_id": t.competition_id, "is_primary_team": t.is_primary_team}
        for t in db.query(Team).all()
    ]
