# MoodMix

Background music discovery app. Find 1-hour YouTube mixes based on mood using 3 sliders (sad/happy, chill/dynamic, organic/electronic), genre filters, and an AI-powered natural language search.

## Tech Stack

### Backend
- **FastAPI** — async REST API
- **SQLAlchemy** — async ORM with `asyncpg` driver
- **PostgreSQL + pgvector** — vector similarity search on mood vectors
- **Alembic** — database migrations
- **Celery + Redis** — background task queue (crawl, classify, analytics)
- **httpx** — async HTTP client for YouTube API + LLM calls
- **pandas** — catalog analytics (mood coverage, genre distribution, gap detection)
- **slowapi** — rate limiting on AI search endpoint
- **pytest** — unit + integration tests

### Frontend
- **React 19** + **TypeScript** — UI
- **Vite** — build tool
- **Zustand** — state management
- **Tailwind CSS** — styling
- **Framer Motion** — animations

### Infrastructure
- **Docker** + **Docker Compose** — containerized deployment
- **GitHub Actions** — CI/CD pipeline
- **nginx** — reverse proxy + SSL termination
- **Supabase** — managed PostgreSQL (production)

## Key Features

- **Mood-based search** — 3 sliders map to a 3D vector, pgvector finds the closest mixes via cosine similarity
- **AI search bar** — natural language queries ("chill rainy day jazz") converted to mood vectors via LLM
- **Genre filtering** — 14 background-music genres, multi-select
- **Vocal toggle** — filter instrumental-only or include mixes with vocals
- **Inline YouTube playback** — persistent bottom player bar, search while listening
- **Automated data pipeline** — crawls YouTube channels, classifies mixes via LLM, checks availability
- **Catalog analytics** — pandas-powered reports on mood space coverage and gap detection
- **MCP server** — AI agent integration for catalog administration via Claude Desktop

## Getting Started

### Prerequisites
- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker (for local PostgreSQL + pgvector)

### Setup

```bash
# Clone and navigate to backend
cd backend

# Install dependencies
uv sync

# Start local database (PostgreSQL + pgvector)
cd ..
docker compose -f docker-compose.dev.yml up -d

# Copy environment variables
cp .env.example .env

# Run database migrations
cd backend
uv run alembic upgrade head

# Start the API server
uv run uvicorn app.main:app --reload
```

API available at `http://localhost:8000` — Swagger docs at `http://localhost:8000/docs`.
