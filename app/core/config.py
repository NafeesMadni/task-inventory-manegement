from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = Field(alias="APP_NAME", default="Inventory Manager")
    DATABASE_URL: str = Field(alias="DATABASE_URL")

    JWT_SECRET_KEY: str = Field(alias="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    ALGORITHM: str = Field(alias="ALGORITHM")

    GMAIL_USER: str = Field(alias="GMAIL_USER")
    GMAIL_PASSWORD: str = Field(alias="GMAIL_PASSWORD")
    GMAIL_HOST: str = Field(alias="GMAIL_HOST", default="smtp.gmail.com")
    GMAIL_PORT: int = Field(alias="GMAIL_PORT", default=587)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        """Use asyncpg for plain PostgreSQL URLs and preserve other schemes."""
        for scheme in ("postgres://", "postgresql://"):
            if value.startswith(scheme):
                return value.replace(scheme, "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    """Load and cache application settings from the environment and .env file."""
    return Settings()  # type: ignore
