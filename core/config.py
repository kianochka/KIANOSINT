from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_token: str = ""
    admin_user_id: int = 0
    database_url: str = "sqlite+aiosqlite:///./kianosint.db"
    redis_url: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    daily_search_limit: int = 2
    request_timeout: int = 15
    max_concurrent_sources: int = 20
    cache_ttl: int = 3600
    github_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    youtube_api_key: str = ""
    hunter_api_key: str = ""
    shodan_api_key: str = ""
    brave_api_key: str = ""
    numverify_api_key: str = ""

    @field_validator(
        "admin_user_id",
        "daily_search_limit",
        "request_timeout",
        "max_concurrent_sources",
        "cache_ttl",
        mode="before",
    )
    @classmethod
    def _empty_int_to_default(cls, v: Any, info):
        if v == "" or v is None:
            defaults = {
                "admin_user_id": 0,
                "daily_search_limit": 2,
                "request_timeout": 15,
                "max_concurrent_sources": 20,
                "cache_ttl": 3600,
            }
            return defaults.get(info.field_name, 0)
        return v

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgres")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()