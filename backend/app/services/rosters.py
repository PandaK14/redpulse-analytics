"""Who counts as a team's player. Player.team_id is a single value recorded
when we first saw someone, so it goes stale the moment a player changes club
(a signing from another EuroCup side keeps his old team_id). The box scores
know better: PlayerGameStats.team_id is the team he actually played for."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Game, Player, PlayerGameStats


def team_player_ids(db: Session, team_id: str, season: Optional[str] = None) -> set:
    """Players who played for the team (in the season, if given), plus anyone
    still filed under the team."""
    query = db.query(PlayerGameStats.player_id).filter(PlayerGameStats.team_id == team_id)
    if season:
        query = query.join(Game, Game.id == PlayerGameStats.game_id).filter(Game.season == season)
    ids = {player_id for (player_id,) in query.distinct().all()}
    ids.update(player_id for (player_id,) in db.query(Player.id).filter(Player.team_id == team_id).all())
    return ids
