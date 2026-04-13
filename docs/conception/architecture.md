# MoodMix — Architecture

## System overview

```
          ┌──────────────┐          ┌──────────────┐
          │   Browser    │          │  Cloudflare  │
          │  React SPA   │          │  Pages       │
          │  (moodmix.fm)│          │  (frontend)  │
          └──────┬───────┘          └──────────────┘
                 │ HTTPS
                 ▼
          ┌──────────────┐
          │  Cloudflare  │
          │  Proxy (SSL) │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │    nginx     │
          │  (reverse    │
          │   proxy)     │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────┐
          │ FastAPI  │
          │ (uvicorn)│
          └────┬─────┘
               │
               ▼
        ┌─────────────────────────┐
        │  PostgreSQL (Docker)    │
        │  pgvector/pgvector:pg17 │
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
| **Python 3.14** | Language | Modern async support, rich AI/data ecosystem, fast to iterate |
| **FastAPI** | Web framework | Async-native, auto OpenAPI docs, Pydantic validation, lightweight |
| **uvicorn** | ASGI server | Production-grade, async, pairs with FastAPI |
| **SQLAlchemy (async)** | ORM | Industry standard, async support via `asyncpg` driver |
| **Alembic** | DB migrations | Native SQLAlchemy integration |
| **httpx** | HTTP client | Async, modern, for YouTube API + LLM API calls |
| **slowapi** | Rate limiting | FastAPI-native, per-IP limiting on AI search |
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
        float mood
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
| **PostgreSQL 17** | Primary database | Robust, supports pgvector extension |
| **pgvector** | Vector similarity search | L2 distance on 3D mood vectors, HNSW index |

### Infrastructure

| Technology | Role | Why |
|---|---|---|
| **Hetzner VPS** | Server | 2 vCPU (Ampere), 4GB RAM — already owned |
| **Docker** | Containerization | Reproducible builds, multi-service via docker-compose |
| **Docker Compose** | Orchestration | 2 services: db (pgvector) + api (FastAPI) |
| **nginx** | Reverse proxy | Forwards to FastAPI on localhost:8000, already on VPS |
| **Cloudflare** | DNS + SSL + WAF | Proxy for public SSL, rate limiting on admin login |
| **Cloudflare Pages** | Frontend hosting | Free tier, auto-deploys from git |
| **GitHub Actions** | CI/CD | Test in Docker, deploy via SSH on push to main |

### External APIs

| API | Role | Cost |
|---|---|---|
| **YouTube Data API v3** | Discover + crawl mixes | Free (10K units/day) |
| **Claude Haiku or OpenAI OSS GPT-120B** | Classify mixes (mood, genre, vocals) | ~$0-0.10/mo |
| **Claude Haiku or OpenAI OSS GPT-120B** | AI search (natural language → mood vector) | Rate limited, minimal cost |

### Future additions

| Technology | Role | Phase |
|---|---|---|
| **Celery + Redis** | Task queue + cache + broker | Phase 8 |
| **MCP SDK** | AI agent integration (catalog admin via Claude Desktop) | Phase 10 |

## Docker Compose services (production)

```yaml
# docker-compose.prod.yml
services:
  db:         # pgvector/pgvector:pg17 (healthcheck, persistent volume)
  api:        # FastAPI + uvicorn (127.0.0.1:8000, env_file: .env.prod)
```

## Data flow

### User searches (slider/genre)
```
Browser → Cloudflare → nginx → FastAPI → pgvector query → PostgreSQL → return
```

### User searches (AI search bar)
```
Browser → Cloudflare → nginx → FastAPI → rate limit check
                                              ├─ BLOCKED → 429
                                              └─ OK → LLM API (text → mood vector)
                                                          → pgvector query → PostgreSQL → return
```

### Pipeline: discover new mixes (manual/scheduled)
```
crawler_service → YouTube Data API v3
                      → filter (duration, embeddable, views)
                      → insert into PostgreSQL
```

### Pipeline: classify pending mixes (manual/scheduled)
```
classifier_service → fetch pending mixes from PostgreSQL
                          → LLM API (metadata → mood vector + genres + vocals)
                          → update mix in PostgreSQL
```

### Pipeline: check availability (manual/scheduled)
```
crawler_service → fetch batch of mixes from PostgreSQL
                      → YouTube Data API (videos.list)
                      → mark unavailable mixes
```
