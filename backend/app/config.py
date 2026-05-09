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

    # Branding for transactional emails
    APP_NAME: str = "MoodMix"
    APP_LOGO_URL: str = ""  # Publicly-reachable URL; leave empty to omit the logo.

    # Email sign-in codes
    AUTH_FROM_EMAIL: str = ""
    EMAIL_CODE_TTL_MINUTES: int = 10
    EMAIL_CODE_MAX_ATTEMPTS: int = 5

    # Auth cookies — both access and refresh are HttpOnly. The access cookie is
    # sent on every API request (path=/api); the refresh cookie is scoped to
    # the auth router (path=/api/auth) so it never leaves that surface.
    ACCESS_COOKIE_NAME: str = "moodmix_access"
    REFRESH_COOKIE_NAME: str = "moodmix_refresh"
    AUTH_COOKIE_SECURE: bool = True
    AUTH_COOKIE_SAMESITE: str = "lax"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""  # e.g. http://localhost:8000/api/auth/google/callback
    # Where the backend redirects after a successful (or failed) OAuth callback.
    FRONTEND_URL: str = "http://localhost:5173"

    # Spotify (Client Credentials flow — app-level auth, no user login)
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": os.getenv("ENV_FILE", ".env")}


settings = Settings()  # type: ignore[call-arg]  # DATABASE_URL loaded from env file at runtime
