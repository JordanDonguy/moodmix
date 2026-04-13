from contextlib import asynccontextmanager
import logging

# Route app logs through uvicorn's colored handler
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app").handlers = logging.getLogger("uvicorn").handlers

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.admin import setup_admin
from app.config import settings
from app.database import engine
from app.exceptions import AppException
from app.routers import admin, genres, health, mixes
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

# Exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Routers
app.include_router(health.router)
app.include_router(genres.router)
app.include_router(mixes.router)
app.include_router(admin.router)

# Admin panel
setup_admin(app)
