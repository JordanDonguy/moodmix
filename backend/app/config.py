from functools import cached_property

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    YOUTUBE_API_KEY: str = ""
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""
    ADMIN_API_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:4173"
    ENV: str = "dev"

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]  # DATABASE_URL loaded from .env at runtime
