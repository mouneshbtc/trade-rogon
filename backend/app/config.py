from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Try project root first (..), then current dir — works from both
        # `cd trade-rogon && uvicorn ...` and `cd backend && uvicorn ...`
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ─────────────────────────────────────────────────────────────────
    env: str = "development"
    app_base_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Database ─────────────────────────────────────────────────────────────
    # Store as plain postgresql:// — driver prefixes are computed below
    database_url: str = "postgresql://traderogon:traderogon@localhost:5432/traderogon"

    @computed_field
    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if "+asyncpg" in url:
            return url
        if "+psycopg2" in url:
            return url.replace("+psycopg2", "+asyncpg")
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @computed_field
    @property
    def sync_database_url(self) -> str:
        url = self.database_url
        if "+psycopg2" in url:
            return url
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "+psycopg2")
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── Market data (Databento) ──────────────────────────────────────────────
    databento_api_key: str = ""
    databento_nq_symbol: str = "NQ.c.0"
    databento_es_symbol: str = "ES.c.0"
    databento_dataset: str = "GLBX.MDP3"

    # ── Observability ─────────────────────────────────────────────────────────
    sentry_dsn: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
