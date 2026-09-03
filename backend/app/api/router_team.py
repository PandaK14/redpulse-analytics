from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Team
from app.schemas.analytics import LineupRow, OnOffRow, RosterPlayer, ShotChartResponse, TeamGame, TeamOverview, TeamSplits
from app.services import lineups as lineups_svc
from app.services import shot_chart as shot_chart_svc
from app.services import team_overview as svc

router = APIRouter()


def _overview_with_league_context(db: Session, team_id: str, competition: Optional[str]) -> dict:
    overview = svc.team_overview(db, team_id, competition)
    overview["league_avg_four_factors"] = svc.competition_average_four_factors(db, "WINNER_LEAGUE")
    overview["eurocup_avg_four_factors"] = svc.competition_average_four_factors(db, "EUROCUP")
    return overview


@router.get("/{team_id}/overview", response_model=TeamOverview)
def get_team_overview(team_id: str, competition: Optional[str] = "ALL", db: Session = Depends(get_db)):
    return _overview_with_league_context(db, team_id, competition)


@router.get("/{team_id}/splits", response_model=TeamSplits)
def get_team_splits(team_id: str, db: Session = Depends(get_db)):
    return {
        "winner_league": _overview_with_league_context(db, team_id, "WINNER_LEAGUE"),
        "eurocup": _overview_with_league_context(db, team_id, "EUROCUP"),
    }


@router.get("/{team_id}/roster", response_model=list[RosterPlayer])
def get_team_roster(team_id: str, db: Session = Depends(get_db)):
    return svc.team_roster_with_averages(db, team_id)


@router.get("/{team_id}/games", response_model=list[TeamGame])
def get_team_games(team_id: str, db: Session = Depends(get_db)):
    return svc.team_games(db, team_id)


@router.get("/{team_id}/lineups", response_model=list[LineupRow])
def get_team_lineups(
    team_id: str,
    size: int = Query(5, ge=2, le=5, description="Lineup size: 5, 3, or 2"),
    min_minutes: float = Query(0.0, ge=0),
    db: Session = Depends(get_db),
):
    return lineups_svc.lineup_table(db, team_id, size=size, min_minutes=min_minutes)


@router.get("/{team_id}/onoff", response_model=list[OnOffRow])
def get_team_onoff(team_id: str, db: Session = Depends(get_db)):
    return lineups_svc.on_off_table(db, team_id)


@router.get("/{team_id}/shots", response_model=ShotChartResponse)
def get_team_shots(team_id: str, competition: str = Query("WINNER_LEAGUE"), db: Session = Depends(get_db)):
    zones = shot_chart_svc.team_shot_zones(db, team_id, competition)
    league_avg = shot_chart_svc.competition_average_shot_zones(db, competition) if competition != "ALL" else None
    return {"zones": zones, "league_avg_zones": league_avg}


@router.get("")
def list_teams(db: Session = Depends(get_db)):
    return [
        {"id": t.id, "name": t.name, "short_name": t.short_name, "competition_id": t.competition_id, "is_primary_team": t.is_primary_team}
        for t in db.query(Team).all()
    ]
