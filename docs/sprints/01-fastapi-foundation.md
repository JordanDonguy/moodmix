# Sprint 1 — FastAPI Foundation

**Goal:** Bootable FastAPI app with local dev DB and all tables created.

## Tasks

### 1.1 — Project initialization
- [ ] Create `backend/` directory
- [ ] Init project with `uv init` (or `poetry init`)
- [ ] Add dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pgvector`, `pydantic-settings`, `httpx`, `python-dotenv`
- [ ] Create `.env.example` with all required env vars (documented, no secrets)
- [ ] Add `.gitignore` (Python defaults + `.env`)

**Files created:**
```
backend/
├── pyproject.toml
├── .env.example
└── .gitignore
```

### 1.2 — Local dev database (Docker)
- [ ] `docker-compose.dev.yml` at project root:
  ```yaml
  services:
    db:
      image: pgvector/pgvector:pg16
      environment:
        POSTGRES_DB: moodmix
        POSTGRES_USER: moodmix
        POSTGRES_PASSWORD: moodmix
      ports:
        - "5432:5432"
      volumes:
        - pgdata:/var/lib/postgresql/data
  volumes:
    pgdata:
  ```
- [ ] Run `docker compose -f docker-compose.dev.yml up -d` → Postgres + pgvector running locally
- [ ] Dev `.env`: `DATABASE_URL=postgresql+asyncpg://moodmix:moodmix@localhost:5432/moodmix`
- [ ] Prod `.env` (on VPS): `DATABASE_URL=postgresql+asyncpg://...@db.xxx.supabase.co:5432/postgres`
- [ ] Same migrations run in both environments — Alembic doesn't care which DB it points to

**Files created:**
```
docker-compose.dev.yml
```

### 1.3 — Configuration
- [ ] `app/config.py` — pydantic-settings `Settings` class
  - `DATABASE_URL: str` (local in dev, Supabase in prod)
  - `YOUTUBE_API_KEY: str`
  - `LLM_API_KEY: str`
  - `LLM_API_URL: str`
  - `ADMIN_API_KEY: str`
  - `CORS_ORIGINS: list[str]`
  - `ENV: str` (dev / prod)
- [ ] Load from `.env` file, fail fast on missing required vars
- [ ] Verify it works: `python -c "from app.config import settings; print(settings.ENV)"`

**Files created:**
```
app/config.py
.env          (local, gitignored)
```

### 1.4 — Database connection
- [ ] `app/database.py` — SQLAlchemy async engine + session factory
  - `create_async_engine(settings.DATABASE_URL)`
  - `async_sessionmaker` for dependency injection
  - `get_db()` async generator for FastAPI `Depends()`
- [ ] Verify connection: write a quick test script that connects and runs `SELECT 1`

> **Pattern: Dependency Injection** — `get_db()` is a FastAPI dependency. Routers never create sessions directly — they receive them via `Depends(get_db)`. This makes testing easy (override the dependency with a test DB session).

**Files created:**
```
app/database.py
```

### 1.5 — Alembic setup + initial migration
- [ ] `alembic init alembic` — initialize Alembic in `backend/`
- [ ] Configure `alembic/env.py` to use async engine from `app/database.py`
- [ ] Configure `alembic.ini` to read DB URL from env
- [ ] Create first migration from `docs/schema.sql`:
  - `genres` table + seed data (14 genres)
  - `mixes` table + pgvector index
  - `mix_genres` table + index
  - `seed_channels` table
  - `pipeline_runs` table + enums + index
- [ ] Run migration against local dev DB: `alembic upgrade head`
- [ ] Verify: connect to local Postgres, tables exist, genres are seeded

**Files created:**
```
alembic.ini
alembic/
├── env.py
├── script.py.mako
└── versions/
    └── 001_initial_schema.py
```

### 1.6 — SQLAlchemy models
- [ ] `app/models/genre.py` — `Genre` model (id, name, slug, created_at)
- [ ] `app/models/mix.py` — `Mix` model (all columns from schema, pgvector column type)
- [ ] `app/models/mix_genre.py` — `MixGenre` association table
- [ ] `app/models/seed_channel.py` — `SeedChannel` model
- [ ] `app/models/pipeline_run.py` — `PipelineRun` model
- [ ] `app/models/__init__.py` — re-export all models

> **Pattern: Single Responsibility** — Each model file owns one table. No god-model file with everything in it. Models only define schema + relationships, no business logic.

**Files created:**
```
app/models/
├── __init__.py
├── genre.py
├── mix.py
├── mix_genre.py
├── seed_channel.py
└── pipeline_run.py
```

### 1.7 — FastAPI app scaffold
- [ ] `app/main.py` — FastAPI app instance
  - Lifespan handler (startup: log connection OK, shutdown: dispose engine)
  - CORS middleware configured from `settings.CORS_ORIGINS`
  - Include routers (empty for now, just wire them up)
- [ ] A single `GET /api/health` endpoint that returns `{ "status": "healthy" }`
- [ ] Run: `uvicorn app.main:app --reload` → verify Swagger UI at `/docs`

**Files created:**
```
app/main.py
app/routers/__init__.py
app/routers/health.py
```

### 1.8 — Exception handling
- [ ] `app/exceptions.py` — custom exception classes:
  - `AppException` base class with `status_code` and `message`
  - `MixNotFoundException(AppException)` — 404
  - `ChannelAlreadyExistsException(AppException)` — 409
  - `RateLimitExceededException(AppException)` — 429
  - `ClassificationError(AppException)` — 500
  - `ExternalAPIError(AppException)` — 502
- [ ] Register a single exception handler for `AppException` in `main.py`
- [ ] Consistent response format: `{ "error": "...", "status": 404, "timestamp": "..." }`

> **Pattern: Open/Closed + Liskov Substitution** — All exceptions inherit from `AppException`. Adding a new error type = new subclass, no modification to the handler. The handler works with any `AppException` subclass uniformly.

**Files created:**
```
app/exceptions.py
```

## Done when

- [ ] `uvicorn app.main:app --reload` starts without errors
- [ ] `/docs` shows Swagger UI with `/api/health` endpoint
- [ ] `/api/health` returns `200 { "status": "healthy" }`
- [ ] Local dev DB has all 5 tables (via `docker compose -f docker-compose.dev.yml up`)
- [ ] `genres` table has 14 rows
- [ ] Custom exceptions return consistent JSON format
