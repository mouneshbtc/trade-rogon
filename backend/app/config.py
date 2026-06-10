from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://localhost:3001"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        """Allow CORS_ORIGINS as a comma-separated string (e.g. "a,b") in
        addition to a JSON array — pydantic-settings' default env format."""
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

    # ── Database ─────────────────────────────────────────────────────────────
    # Store as plain postgresql:// — driver prefixes are computed below
    database_url: str = "postgresql://traderogon:traderogon@localhost:5432/traderogon"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if "+psycopg2" in url:
            url = url.replace("+psycopg2", "+asyncpg")
        elif "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # asyncpg's connect() accepts `ssl=`, not `sslmode=`, and has no
        # `channel_binding` parameter at all. Neon's connection strings include
        # `?sslmode=require&channel_binding=require`, which psycopg2 (used for
        # `sync_database_url`/Alembic) accepts natively via libpq but asyncpg
        # rejects both with a TypeError. Rename `sslmode`->`ssl` (preserving its
        # value) and drop `channel_binding`, for the async URL only.
        split = urlsplit(url)
        query = parse_qsl(split.query, keep_blank_values=True)
        new_query = [
            ("ssl" if key == "sslmode" else key, value) for key, value in query if key != "channel_binding"
        ]
        if new_query != query:
            split = split._replace(query=urlencode(new_query))
            url = urlunsplit(split)

        return url

    @computed_field  # type: ignore[prop-decorator]
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
