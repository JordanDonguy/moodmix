# MoodMix

Background music discovery app. Find 1-hour YouTube mixes based on mood using 3 sliders (sad/happy, chill/dynamic, organic/electronic), genre filters, and an AI-powered natural language search.

## Tech Stack

### Backend
- **FastAPI** - async REST API
- **SQLAlchemy** - async ORM with `asyncpg` driver
- **PostgreSQL + pgvector** - vector similarity search on mood vectors
- **Alembic** - database migrations
- **httpx** - async HTTP client for YouTube API + LLM calls
- **slowapi** - rate limiting on AI search endpoint
- **SQLAdmin** - admin panel for catalog management
- **pytest** - unit + integration tests

### Frontend
- **React 19** + **TypeScript** - UI
- **Vite** - build tool
- **TanStack Query** - async data fetching + infinite scroll
- **Zustand** - state management
- **React Router** - client-side routing
- **Tailwind CSS 4** - styling
- **Lucide** - icons
- **Biome** - linting + formatting

## Key Features

- **Mood-based search** - 3 sliders map to a 3D vector, pgvector finds the closest mixes via euclidean distance
- **AI search bar** - natural language queries ("chill rainy day jazz") converted to mood vectors via LLM
- **Genre filtering** - 10 background-music genres, multi-select
- **Vocal toggle** - filter instrumental-only or include mixes with vocals
- **Inline YouTube playback** - persistent bottom player bar, search while listening
- **Automated data pipeline** - crawls YouTube channels, classifies mixes via LLM, checks availability

## Getting Started

### Prerequisites
- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+
- Docker (for local PostgreSQL + pgvector)

### Backend

```bash
# Install dependencies
make install

# Start local database (PostgreSQL + pgvector on port 5433)
make db-up

# Copy environment variables and fill in your API keys
cp backend/.env.example backend/.env

# Run database migrations
make migrate

# Start the API server (hot reload)
make dev
```

API available at `http://localhost:8000` — Swagger docs at `http://localhost:8000/docs`.

### Frontend

```bash
# Install dependencies
cd frontend && npm install

# Start the dev server (hot reload)
npm run dev
```

App available at `http://localhost:5173`.

## Testing

Tests use a separate PostgreSQL database running in Docker, with transaction rollback for isolation between tests.

### Setup

```bash
# Start the test database (pgvector on port 5434)
make test-db-up

# Run migrations on the test database
make test-migrate
```

### Running tests

```bash
# Run all tests with coverage report
make test

# Run a specific test file
cd backend && ENV_FILE=.env.test uv run pytest tests/test_mix_service.py -v

# Run a single test
cd backend && ENV_FILE=.env.test uv run pytest tests/test_mix_service.py::TestSearchMixes::test_genre_filter -v
```

### Test structure

```
tests/
├── conftest.py             - Shared fixtures (DB session, HTTP client, seed data)
├── test_youtube_client.py  - Unit tests: pure functions (parsers, helpers)
├── test_mix_service.py     - Service integration tests: real DB, no network
└── test_mixes_router.py    - Route integration tests: full FastAPI stack
```

### How it works

- **Test database**: `docker-compose.test.yml` runs a separate Postgres on port 5434, isolated from the dev database (port 5433).
- **Config switching**: `ENV_FILE=.env.test` tells the app to load `.env.test` instead of `.env`, pointing at the test database with dummy API keys.
- **Transaction rollback**: each test runs inside a database transaction that rolls back after the test. No test data persists - every test gets a clean slate.
- **Dependency overrides**: route tests use FastAPI's `dependency_overrides` to inject the test DB session into the app, so requests go through the full stack but use the rolled-back transaction.
