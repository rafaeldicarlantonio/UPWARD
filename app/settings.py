from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    # Pinecone indices
    PINECONE_EXPLICATE_INDEX: Optional[str] = None
    PINECONE_IMPLICATE_INDEX: Optional[str] = None

    # JWT / Auth
    JWT_SECRET: str = Field(..., description="JWT signing secret")
    JWT_ALGO: str = Field("HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, description="Access token TTL in minutes")

    # Roles
    ROLE_DEFAULT: Literal["general", "pro", "scholar", "analytics", "operations"] = "general"

    # AURA
    AURA_API_BASE: Optional[str] = None
    AURA_API_KEY: Optional[str] = None

    # Database (required for migrations and DSN consumers)
    DATABASE_URL: str = Field(..., description="Postgres connection URL")

    class Config:
        env_file = ".env"
        case_sensitive = True

    @validator("JWT_ALGO")
    def _jwt_algo_upper(cls, v: str) -> str:
        return (v or "HS256").upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
