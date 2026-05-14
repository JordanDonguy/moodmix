from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

# Route app logs through uvicorn's colored handler
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app").handlers = logging.getLogger("uvicorn").handlers

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.admin import setup_admin
from app.config import settings
from app.database import engine
from app.exceptions import AppException
from app.routers import admin, auth, contact, genres, health, mixes, playback
from app.routers.mixes import limiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MoodMix API (env=%s)", settings.ENV)
    yield
    await engine.dispose()
    logger.info("MoodMix API shut down")


app = FastAPI(
    title="MoodMix API",
    description="Background music discovery via mood-based vector search",
    version="0.1.0",
    lifespan=lifespan,
)

# Session (required for sqladmin auth)
app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_API_KEY)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers — every error path produces the same envelope shape so
# clients can parse uniformly regardless of which layer raised.
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=AppException(str(exc.detail), exc.status_code).to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # input/ctx dropped from per-field errors to avoid leaking submitted data
    # (e.g. attempted passwords) back into the error response.
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "status": 422,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "errors": [
                {"type": e["type"], "loc": e["loc"], "msg": e["msg"]}
                for e in exc.errors()
            ],
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content=AppException(f"Rate limit exceeded: {exc.detail}", 429).to_dict(),
    )


app.state.limiter = limiter

# Routers
app.include_router(health.router)
app.include_router(genres.router)
app.include_router(mixes.router)
app.include_router(contact.router)
app.include_router(auth.router)
app.include_router(playback.router)
app.include_router(admin.router)

# Admin panel
setup_admin(app)
