from typing import Optional

from pydantic import BaseModel


class FourFactors(BaseModel):
    efg_pct: float
    tov_pct: float
    orb_pct: float
    ftr: float


class TeamOverview(BaseModel):
    games_played: int
    wins: Optional[int] = None
    losses: Optional[int] = None
    points_for_avg: Optional[float] = None
    points_against_avg: Optional[float] = None
    ortg: Optional[float] = None
    drtg: Optional[float] = None
    net_rating: Optional[float] = None
    pace: Optional[float] = None
    four_factors: Optional[FourFactors] = None
    league_avg_four_factors: Optional[FourFactors] = None
    eurocup_avg_four_factors: Optional[FourFactors] = None


class TeamSplits(BaseModel):
    winner_league: TeamOverview
    eurocup: TeamOverview


class RosterPlayer(BaseModel):
    player_id: str
    name: str
    position: Optional[str] = None
    jersey_number: Optional[int] = None
    games_played: int
    mpg: float
    ppg: float
    rpg: float
    apg: float
    ts_pct: float
    usg_pct: float
    ast_to: float


class GameLogEntry(BaseModel):
    game_id: str
    game_date: str
    opponent_name: str
    result: str
    minutes_played: float
    points: int
    reb: int
    assists: int
    fg2m: int
    fg2a: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int
    steals: int
    turnovers: int
    blocks: int
    valuation: int


class RollingFormPoint(BaseModel):
    game_date: str
    points: int
    rolling_ppg: float
    rolling_ts_pct: float


class PlayerProfile(BaseModel):
    player_id: str
    name: str
    position: Optional[str] = None
    jersey_number: Optional[int] = None
    height_cm: Optional[int] = None
    team_id: str
    games_played: int
    mpg: float
    ppg: float
    rpg: float
    apg: float
    ts_pct: float
    usg_pct: float
    ast_to: float
    game_log: list[GameLogEntry]
    rolling_form: list[RollingFormPoint]


class TeamGame(BaseModel):
    game_id: str
    competition_id: str
    round: Optional[str] = None
    game_date: str
    opponent_name: str
    is_home: bool
    team_score: int
    opponent_score: int
    result: str


class LineupRow(BaseModel):
    player_ids: list[str]
    player_names: list[str]
    minutes: float
    possessions: float
    ortg: float
    drtg: float
    net_rating: float
    plus_minus: int


class OnOffRow(BaseModel):
    player_id: str
    name: str
    minutes_on: float
    minutes_off: float
    net_rating_on: Optional[float] = None
    net_rating_off: Optional[float] = None
    on_off_diff: Optional[float] = None


class ShotZoneStat(BaseModel):
    zone: str
    attempts: int
    makes: int
    fg_pct: float
    volume_pct: float
    points_per_shot: float


class ShotChartResponse(BaseModel):
    zones: list[ShotZoneStat]
    league_avg_zones: Optional[list[ShotZoneStat]] = None
