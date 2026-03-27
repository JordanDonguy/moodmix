from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine
from app.exceptions import AppException
from app.routers import admin, health

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

# Routers
app.include_router(health.router)
app.include_router(admin.router)
