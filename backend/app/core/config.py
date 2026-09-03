from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RedPulse Analytics API"
    database_url: str = "sqlite:///./redpulse.db"
    use_mock_data: bool = False
    current_season: str = "2025-2026"
    winner_league_cyear: int = 2026
    eurocup_season_code: str = "U2025"
    scraper_max_games: Optional[int] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
