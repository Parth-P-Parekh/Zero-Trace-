"""Settings — one source of truth for every environment variable.

CODE-01 §3.2: config fails loudly at startup on a missing required variable.
It never silently defaults a security setting.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env.example carries later-milestone vars on purpose
    )

    # --- core ---
    env: Literal["dev", "demo", "prod"] = "dev"
    log_level: str = "info"
    default_tenant: str = "acme-tech"  # dev-only fallback; demo/prod require X-ZeroTrace-Tenant

    # --- datastores ---
    pg_dsn: str = Field(default="postgresql+asyncpg://zt:zt@postgres:5432/zerotrace")
    redis_url: str | None = "redis://redis:6379/0"

    # --- identity (C22) ---
    oidc_issuer: str = "http://oidc-stub:9000"
    oidc_client_id: str = "zerotrace"
    oidc_client_secret: str = "dev-not-a-secret"
    dev_token_prefix: str = "dev:"

    # --- budgets ---
    budget_s4_ms: int = 2

    # --- upstream ---
    upstream: Literal["stub", "passthrough"] = "stub"
    upstream_base_url: str | None = None
    upstream_timeout_s: int = 30

    @field_validator("pg_dsn")
    @classmethod
    def _dsn_must_be_async(cls, v: str) -> str:
        ok = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not v.startswith(ok):
            raise ValueError(
                f"ZT_PG_DSN must use an async driver, one of {ok}. Got: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _security_settings_are_explicit(self) -> "Settings":
        # A security setting is never guessed. If the operator asks for a real
        # upstream, they must say where it is.
        if self.upstream == "passthrough" and not self.upstream_base_url:
            raise ValueError(
                "ZT_UPSTREAM=passthrough requires ZT_UPSTREAM_BASE_URL. "
                "Refusing to start with an undefined upstream."
            )
        if self.env == "prod" and self.dialect == "sqlite":
            raise ValueError(
                "SQLite is a dev/test dialect only (SUBMISSION.md). "
                "ZT_ENV=prod requires Postgres."
            )
        if self.env == "prod" and self.oidc_client_secret == "dev-not-a-secret":
            raise ValueError("ZT_OIDC_CLIENT_SECRET is still the dev placeholder.")
        return self

    @property
    def dialect(self) -> str:
        """'postgresql' or 'sqlite' — the data layer branches on this."""
        return "sqlite" if self.pg_dsn.startswith("sqlite") else "postgresql"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Tests call this after changing the environment."""
    get_settings.cache_clear()
