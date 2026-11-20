from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = Field(alias="APP_NAME", default="Inventory Manager")

    DATABASE_URL: str = Field(alias="DATABASE_URL")

    ALGORITHM: str = Field(alias="ALGORITHM")
    JWT_SECRET_KEY: str = Field(alias="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    GMAIL_USER: str = Field(alias="GMAIL_USER")
    GMAIL_PASSWORD: str = Field(alias="GMAIL_PASSWORD")
    GMAIL_PORT: int = Field(alias="GMAIL_PORT", default=587)
    GMAIL_HOST: str = Field(alias="GMAIL_HOST", default="smtp.gmail.com")

    TWO_FACTOR_ENCRYPTION_KEY: str = Field(alias="TWO_FACTOR_ENCRYPTION_KEY")

    INITIAL_ADMIN_EMAIL: str = Field(alias="INITIAL_ADMIN_EMAIL")
    INITIAL_ADMIN_PASSWORD: str = Field(alias="INITIAL_ADMIN_PASSWORD")

    CELERY_RESULT_BACKEND: str = Field(
        alias="CELERY_RESULT_BACKEND", default="redis://localhost:6379/0"
    )
    CELERY_BROKER_URL: str = Field(
        alias="CELERY_BROKER_URL", default="redis://localhost:6379/0"
    )

    SESSION_SECRET: str = Field(alias="SESSION_SECRET")

    GOOGLE_CLIENT_ID: str = Field(alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(alias="GOOGLE_CLIENT_SECRET")

    TURNSTILE_SITE_KEY: str = Field(alias="TURNSTILE_SITE_KEY")
    TURNSTILE_SECRET_KEY: str = Field(alias="TURNSTILE_SECRET_KEY")
    SITEVERIFY_URL: str = Field(alias="SITEVERIFY_URL")

    OPENROUTER_API_KEY: str = Field(alias="OPENROUTER_API_KEY")

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
