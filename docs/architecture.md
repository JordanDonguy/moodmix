# MoodMix — Architecture

## System overview

```
                         ┌──────────────┐
                         │   Browser    │
                         │  React SPA   │
                         └──────┬───────┘
                                │ HTTPS
                                ▼
                         ┌──────────────┐
                         │    nginx     │
                         │  (reverse    │
                         │   proxy +    │
                         │   SSL +      │
                         │   static)    │
                         └──────┬───────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
                 ▼              ▼              ▼
          /api/*          /            MCP server
          ┌──────────┐   static       ┌──────────┐
          │ FastAPI  │   files        │ MCP SDK  │
          │ (uvicorn)│                │ (stdio)  │
          └────┬─────┘                └────┬─────┘
               │                           │
          ┌────┴─────────────┐             │
          │                  │             │
          ▼                  ▼             │
   ┌────────────┐    ┌────────────┐        │
   │   Redis    │    │  Celery    │        │
   │  (cache +  │◄───│  worker +  │        │
   │   broker)  │    │  beat      │        │
   └────────────┘    └─────┬──────┘        │
                           │               │
                           ▼               ▼
                    ┌─────────────────────────┐
                    │  Supabase PostgreSQL    │
                    │  (pgvector)             │
                    └─────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
             ┌────────────┐         ┌────────────┐
             │ YouTube    │         │ LLM API    │
             │ Data API   │         │ (Haiku /   │
             │ v3         │         │  GPT-120B) │
             └────────────┘         └────────────┘
```

## Tech stack

### Backend

| Technology | Role | Why |
|---|---|---|
| **Python 3.12+** | Language | Modern async support, rich AI/data ecosystem, fast to iterate |
| **FastAPI** | Web framework | Async-native, auto OpenAPI docs, Pydantic validation, lightweight |
| **uvicorn** | ASGI server | Production-grade, async, pairs with FastAPI |
| **SQLAlchemy (async)** | ORM | Industry standard, async support via `asyncpg` driver |
| **Alembic** | DB migrations | Native SQLAlchemy integration |
| **Celery** | Task queue | Production-grade background jobs, scheduling via Beat |
| **Redis** | Cache + broker | Search result caching (TTL), Celery message broker |
| **httpx** | HTTP client | Async, modern, for YouTube API + LLM API calls |
| **slowapi** | Rate limiting | FastAPI-native, per-IP limiting on AI search |
| **pandas** | Data analysis | Catalog analytics: mood coverage, genre distribution, gap detection |
| **pydantic-settings** | Configuration | Typed env vars, `.env` file support, validation at startup |
| **pytest** | Testing | Unit + integration tests, async support via `pytest-asyncio` |

### Frontend

| Technology | Role | Why |
|---|---|---|
| **React 19+** | UI framework | Component model, ecosystem |
| **TypeScript** | Language | Type safety, better DX |
| **Vite** | Build tool | Fast dev server, optimized builds |
| **Zustand** | State management | Lightweight, minimal boilerplate for slider/genre/player state |
| **Tailwind CSS** | Styling | Utility-first, fast iteration, responsive grid out of the box |
| **Framer Motion** | Animations | Smooth transitions for card playback swap, slider interactions, loading states |

### Database
erDiagram
    genres {
        uuid id PK
        text name UK
        text slug UK
        timestamptz created_at
    }

    mixes {
        uuid id PK
        text youtube_id UK
        text title
        text channel_name
        text channel_id
        text description
        text[] tags
        integer duration_seconds
        text thumbnail_url
        timestamptz published_at
        integer view_count
        vector(3) mood_vector
        float valence
        float energy
        float instrumentation
        boolean has_vocals
        float classification_confidence
        timestamptz created_at
        timestamptz unavailable_at
    }

    mix_genres {
        uuid mix_id FK
        uuid genre_id FK
    }

    seed_channels {
        uuid id PK
        text channel_id UK
        text channel_name
        text uploads_playlist_id
        boolean active
        timestamptz last_crawled_at
        integer total_mixes_found
        timestamptz created_at
    }

    pipeline_runs {
        uuid id PK
        pipeline_type pipeline_type
        pipeline_run_status status
        timestamptz started_at
        timestamptz completed_at
        integer mixes_processed
        integer mixes_added
        text error_message
        jsonb metadata
    }

    mixes ||--o{ mix_genres : "has"
    genres ||--o{ mix_genres : "has"
| Technology | Role | Why |
|---|---|---|
| **PostgreSQL 16+** | Primary database | Robust, supports pgvector extension |
| **pgvector** | Vector similarity search | Cosine similarity on 3D mood vectors, HNSW index |
| **Supabase** | Managed hosting | Free tier (500MB, 60 connections), managed backups, dashboard |

### Infrastructure

| Technology | Role | Why |
|---|---|---|
| **Hetzner VPS** | Server | 2 vCPU (Ampere), 4GB RAM — already owned |
| **Docker** | Containerization | Reproducible builds, multi-service via docker-compose |
| **Docker Compose** | Orchestration | 4 services: api, worker, beat, redis |
| **nginx** | Reverse proxy | SSL termination, static file serving, already on VPS |
| **Let's Encrypt** | SSL | Free HTTPS via certbot |
| **GitHub Actions** | CI/CD | Build, test, deploy on push to main |
| **ghcr.io** | Container registry | Free with GitHub, private images |

### External APIs

| API | Role | Cost |
|---|---|---|
| **YouTube Data API v3** | Discover + crawl mixes | Free (10K units/day) |
| **Claude Haiku or OpenAI OSS GPT-120B** | Classify mixes (mood, genre, vocals) | ~$0-0.10/mo |
| **Claude Haiku or OpenAI OSS GPT-120B** | AI search (natural language → mood vector) | Rate limited, minimal cost |

### Future additions

| Technology | Role | Phase |
|---|---|---|
| **MCP SDK** | AI agent integration (catalog admin via Claude Desktop) | Phase 10 |

## Docker Compose services

```yaml
# Simplified overview — not the actual file
services:
  api:        # FastAPI + uvicorn (port 8000)
  worker:     # Celery worker (crawl, classify, analytics tasks)
  beat:       # Celery Beat (cron scheduler)
  redis:      # Redis 7 (cache + Celery broker)
```

All services share the same Docker image (different entrypoint commands).
Supabase PostgreSQL is external (not in docker-compose).

## Data flow

### User searches (slider/genre)
```
Browser → nginx → FastAPI → Redis cache?
                                  ├─ HIT → return cached results
                                  └─ MISS → pgvector query → Supabase → cache → return
```

### User searches (AI search bar)
```
Browser → nginx → FastAPI → rate limit check
                                  ├─ BLOCKED → 429
                                  └─ OK → LLM API (text → mood vector)
                                              → pgvector query → Supabase → return
```

### Pipeline: discover new mixes
```
Celery Beat (cron) → Celery worker → YouTube Data API v3
                                          → filter (duration, embeddable, views)
                                          → insert into Supabase (status: pending mood_vector)
```

### Pipeline: classify pending mixes
```
Celery Beat (cron) → Celery worker → fetch pending mixes from Supabase
                                          → LLM API (metadata → mood vector + genres + vocals)
                                          → update mix in Supabase
                                          → invalidate Redis cache
```

### Pipeline: check availability
```
Celery Beat (cron) → Celery worker → fetch batch of mixes from Supabase
                                          → YouTube Data API (videos.list)
                                          → mark unavailable mixes
                                          → invalidate Redis cache
```
