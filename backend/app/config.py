import os
from functools import cached_property

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    YOUTUBE_API_KEY: str = ""
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""
    ADMIN_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    RESEND_API_URL: str = "https://api.resend.com/emails"
    CONTACT_FROM_EMAIL: str = ""
    CONTACT_TO_EMAIL: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:4173"
    ENV: str = "dev"

    # Auth — JWT access tokens + opaque refresh tokens (rotated)
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TTL_MINUTES: int = 15
    REFRESH_TTL_DAYS: int = 30

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": os.getenv("ENV_FILE", ".env")}


settings = Settings()  # type: ignore[call-arg]  # DATABASE_URL loaded from env file at runtime
