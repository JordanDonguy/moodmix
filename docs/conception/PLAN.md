# MoodMix — Background Music Discovery App

## Context

Build an app that helps users find 1-hour background instrumental music mixes (from YouTube) based on mood. Users interact via 3 sliders (sad/happy, chill/dynamic, organic/electronic) and an AI search bar that converts natural language to a mood vector. The core challenge is building a large, automatically-classified catalog without manual curation.

**This project doubles as a learning vehicle for Python FastAPI.**

## Architecture Overview

**Stack:** Python FastAPI (API + data pipeline) + PostgreSQL (pgvector, self-hosted) + React SPA (Vite + TS) + YouTube Data API v3 + LLM classification

```
┌─────────────────────────────────────────────┐
│          React SPA (Vite + TS)              │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  │
│  │ 3 Sliders│  │ AI Search │  │ Player   │  │
│  │ (mood)   │  │ Bar       │  │ (embed)  │  │
│  └────┬─────┘  └─────┬─────┘  └──────────┘  │
└───────┼──────────────┼──────────────────────┘
        │              │
        ▼              ▼
┌─────────────────────────────────────────────┐
│        FastAPI Server (VPS)                 │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ REST API     │  │ Data Pipeline      │   │
│  │ /search      │  │ - YouTube crawler  │   │
│  │ /mixes       │  │ - LLM classifier   │   │
│  │ /ai-search   │  │ - Scheduled jobs   │   │
│  └──────┬───────┘  └─────────┬──────────┘   │
└─────────┼────────────────────┼──────────────┘
          │                    │
          ▼                    ▼
┌─────────────────────────────────────────────┐
│   PostgreSQL (pgvector, Docker)             │
│   - pgvector extension                      │
│   - mixes table + HNSW index                │
│   - seed_channels table                     │
└─────────────────────────────────────────────┘
```

---

## Part 1: FastAPI Project Setup

### Project structure

```
moodmix/
├── .github/workflows/
│   └── deploy.yml                          -- GitHub Actions CI/CD
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml                      -- Dependencies (uv or poetry)
│   ├── alembic.ini                         -- Alembic config
│   ├── alembic/
│   │   └── versions/                       -- Migration files
│   ├── app/
│   │   ├── main.py                         -- FastAPI app, lifespan, CORS, exception handlers
│   │   ├── config.py                       -- pydantic-settings (env vars, typed config)
│   │   ├── database.py                     -- SQLAlchemy async engine + session
│   │   ├── models/
│   │   │   ├── mix.py                      -- SQLAlchemy model
│   │   │   ├── genre.py                    -- Genre model
│   │   │   └── seed_channel.py             -- SeedChannel model
│   │   ├── schemas/
│   │   │   ├── mix.py                      -- Pydantic request/response schemas
│   │   │   ├── genre.py
│   │   │   └── search.py
│   │   ├── routers/
│   │   │   ├── mixes.py                    -- /api/mixes/* endpoints
│   │   │   ├── genres.py                   -- /api/genres endpoint
│   │   │   ├── admin.py                    -- /api/admin/* (API key protected)
│   │   │   └── health.py                   -- /api/health
│   │   ├── services/
│   │   │   ├── mix_service.py              -- Business logic + pgvector queries
│   │   │   ├── crawler_service.py          -- YouTube Data API v3 client
│   │   │   ├── classifier_service.py       -- LLM metadata classification
│   │   │   ├── ai_search_service.py        -- Natural language → mood vector via LLM
│   │   │   └── analytics_service.py        -- Catalog health reports (pandas)
│   │   ├── tasks/
│   │   │   ├── celery_app.py               -- Celery config + Redis broker
│   │   │   └── pipeline_tasks.py           -- Celery tasks: crawl, classify, check availability, analytics
│   │   ├── middleware/
│   │   │   ├── auth.py                     -- API key dependency for admin routes
│   │   │   └── rate_limit.py               -- slowapi rate limiting
│   │   └── exceptions.py                   -- Custom exceptions + handlers
│   └── tests/
│       ├── conftest.py                     -- Fixtures (test DB, async client)
│       ├── test_mixes.py                   -- Search endpoint tests
│       ├── test_classifier.py              -- Unit tests for classifier
│       └── test_mix_service.py             -- Business logic tests
├── mcp_server/
│   ├── server.py                           -- MCP server entrypoint
│   └── tools.py                            -- Tool definitions (search, stats, admin)
├── frontend/                               -- React SPA (Vite + TS)
├── docker-compose.prod.yml                 -- PostgreSQL (pgvector) + FastAPI API
└── README.md
```

### Key Python dependencies
- `fastapi` — Async REST API framework
- `uvicorn` — ASGI server
- `sqlalchemy[asyncio]` — Async ORM (with `asyncpg` driver)
- `alembic` — Database migrations
- `pgvector` — pgvector SQLAlchemy integration
- `pydantic-settings` — Typed config from env vars / `.env` files
- `httpx` — Async HTTP client for YouTube API + LLM calls
- `celery[redis]` — Distributed task queue for pipeline jobs
- `redis` — Caching (search results, genre list)
- `slowapi` — Rate limiting (built on `limits` library)
- `pandas` — Catalog analytics (mood coverage, genre distribution, gap detection)
- `mcp` — MCP server SDK for AI agent integration
- `pytest` + `pytest-asyncio` + `httpx` — Testing

### Database connection
- Self-hosted PostgreSQL with pgvector extension, running in Docker (`pgvector/pgvector:pg17`)
- Configure in `.env` with `DATABASE_URL=postgresql+asyncpg://...`
- Uses `asyncpg` driver for async SQLAlchemy

---

## Part 2: Data Pipeline (the hard problem)

### Step 1 — Discovery: Finding YouTube mixes

**Primary: Channel playlist crawling** (cheapest quota usage)
- Seed a list of ~50-100 known channels (Lofi Girl, Chillhop, relaxdaily, Cafe Music BGM, Yellow Brick Cinema, etc.)
- Use `playlistItems.list` (1 quota unit/call, 50 results/page) to crawl all uploads
- Filter by `duration >= 30min` (via `videos.list`, also 1 unit/50 videos)
- Expected yield: 2,000-5,000 mixes for ~500 quota units total

**Secondary: Keyword search** (30-50 searches/day)
- Queries like "1 hour lo-fi study mix", "ambient electronic instrumental", "chill jazz background"
- Use `search.list` with `videoDuration=long`, `videoCategoryId=10` (Music)
- 100 units/search, budget 30-50/day = 3,000-5,000 units
- Discovers channels not in seed list

**Tertiary: Snowball via related videos**
- `search.list` with `relatedToVideoId` on best mixes
- 10-20/day, discovers new channels organically

**Content quality filtering (two layers):**
- Crawler pre-filter: skip videos with < 1,000 views, skip non-embeddable videos, skip channels that are clearly non-music
- LLM post-filter: classifier prompt includes "is this actually a music mix?" check → mixes flagged `is_valid_mix = false` are excluded from results

**Implementation: `crawler_service.py`**
- Use `httpx.AsyncClient` to call YouTube Data API v3
- Celery Beat schedules tasks via `pipeline_tasks.py`:
  - Weekly: re-crawl all seed channels
  - Daily: run keyword searches with rotating query list
  - Daily: availability check on random subset of catalog

**Total daily quota: ~5,000-8,000 of 10,000 free limit**

### Step 2 — Classification: Automatic mood tagging

Three-layer approach:

#### Layer 1: LLM Metadata Analysis (primary, covers 100% of catalog)

Two-phase approach:

**Phase A — Initial seed (2,000-5,000 mixes): Claude Code + JSON file**
- Crawler exports pending mixes to a JSON file
- Use Claude Code to read the file and classify in batches of ~50-100
- Output written to a result JSON, then imported into PostgreSQL

**Phase B — Ongoing automated classification (~100 mixes/day): `classifier_service.py`**
- Input: title, description, tags, channel name
- Call either Claude Haiku or OpenAI OSS GPT-120B API via `httpx`
- Output: mood vector + confidence score per dimension + genre tags
- Cost: negligible (~$0.10/mo with Haiku, free with OSS GPT-120B if self-hosted)

**Prompt strategy** (same for both phases, chain-of-thought for accuracy):
```
Analyze this YouTube music mix and classify it.

Title: "{{title}}"
Channel: "{{channel}}"
Description: "{{description}}"
Tags: {{tags}}

Step 1: Describe what this mix likely sounds like.
Step 2: Rate each dimension from -1.0 to 1.0 with brief justification:
  - mood: -1 (dark/moody) to +1 (bright/uplifting)
  - energy: -1 (ambient/chill) to +1 (dynamic/driving)
  - instrumentation: -1 (organic/acoustic) to +1 (electronic/synthetic)
Step 3: Confidence (0.0-1.0) for each rating.
Step 4: Pick 1-3 genres from this list: [lo-fi, hip-hop, synthwave,
  chill-electronic, deep-house, drum-and-bass, downtempo, neo-soul-r-and-b,
  reggae-dub, guitar, jazz, blues, ambient, environment]
Step 5: Does this mix contain vocals? Answer true or false.
Step 6: Is this actually a music mix (not a podcast, ASMR, guided meditation, tutorial, etc.)? Answer true/false.

Respond as JSON only.
```

#### Layer 2: Client-side Audio Analysis (future enrichment — currently blocked)
- Original idea: capture audio via Web Audio API when user plays a mix → run Essentia.js (WASM) in-browser
- **Problem:** YouTube IFrame embed is a cross-origin iframe — browser blocks Web Audio API access to its audio output
- **Status:** Not feasible with standard YouTube embeds. Would need an alternative approach (e.g., server-side audio analysis via yt-dlp, which has legal gray area) or a different playback method
- Keeping this as a future consideration — the LLM metadata classification + user feedback may be sufficient

#### Layer 3: User Feedback Loop (future)
- Simple "this feels more chill than shown" corrections
- Track play-through vs. skip (implicit signal)
- Periodically re-calibrate vectors

### Step 3 — Storage: pgvector on PostgreSQL

**Alembic migration:**
```sql
create extension if not exists vector;

create table mixes (
  id uuid primary key default gen_random_uuid(),
  youtube_id text unique not null,
  title text not null,
  channel_name text,
  channel_id text,
  description text,
  tags text[],
  duration_seconds integer,
  thumbnail_url text,
  published_at timestamptz,

  -- Mood vector (for similarity search)
  mood_vector vector(3),

  -- Individual scores (for slider filtering + display)
  mood float,          -- -1 to 1: dark ↔ bright
  energy float,           -- -1 to 1: chill ↔ dynamic
  instrumentation float,  -- -1 to 1: organic ↔ electronic

  -- Vocal classification
  vocal_type text,             -- 'vocal', 'instrumental', 'mostly_instrumental'

  -- Classification metadata
  classification_method text,  -- 'metadata_llm', 'audio_analysis', 'hybrid'
  classification_confidence float,
  is_valid_mix boolean,        -- false if LLM flags it as non-music content (podcast, ASMR, etc.)

  status text default 'pending',
  created_at timestamptz default now()
);

create index on mixes using hnsw (mood_vector vector_cosine_ops);

create table genres (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,       -- e.g. 'lo-fi', 'jazz', 'classical', 'ambient'
  slug text unique not null        -- URL-friendly: 'lo-fi', 'jazz', etc.
);

create table mix_genres (
  mix_id uuid references mixes(id) on delete cascade,
  genre_id uuid references genres(id) on delete cascade,
  primary key (mix_id, genre_id)
);

create index on mix_genres(genre_id);  -- fast lookup: "all mixes in genre X"

create table seed_channels (
  id uuid primary key default gen_random_uuid(),
  channel_id text unique not null,
  channel_name text,
  last_crawled_at timestamptz,
  active boolean default true
);
```

The `genres` table is pre-seeded with 14 genres focused on background music: lo-fi, hip-hop, synthwave, chill electronic, deep house, drum & bass, downtempo, neo-soul/R&B, reggae/dub, guitar, jazz, blues, ambient, environment. The LLM classifier picks from this list — no free-text genres to avoid duplicates like "lo-fi" vs "lofi" vs "Lo-Fi".

**Mood vector axes (3D):**
- **Mood** (dark 🌙 ↔ bright ☀️) — atmosphere/vibe, not sad/happy. Kind of subjective. Synthwave more likely to be dark / night, while bossa nova more likely to be day / bright for example.
- **Energy** (chill 🛋️ ↔ dynamic ⚡) — tempo, intensity, drive.
- **Instrumentation** (organic 🥁 ↔ electronic 💻) — real instruments vs synthesized.

**Deactivatable sliders:**
Each slider can be toggled on/off. Default state = all off → browsing mode (random mixes). User activates only the dimensions they care about.

**Search strategy depending on active sliders:**

```
0 sliders active → random mixes (seeded RANDOM() for stable pagination)
1 slider active  → WHERE + ABS() distance on that column, ORDER BY RANDOM()
2 sliders active → WHERE + ABS() distance on both columns, ORDER BY RANDOM()
3 sliders active → pgvector cosine similarity (full vector search)
```

All cases: results within a ±0.25 range of target value(s), weighted by proximity to center of range (closer = more likely to appear). Random jitter added so results vary but center-biased.

**Session-stable randomness with SETSEED:**
Frontend generates a random seed per session (e.g., `0.42`). Sent with every request.
Same seed = same random order = consistent infinite scroll pagination.
New session (page refresh) = new seed = fresh shuffle.

```sql
SELECT SETSEED(:seed);
SELECT * FROM mixes
WHERE unavailable_at IS NULL
  AND energy BETWEEN :energy - 0.25 AND :energy + 0.25
  AND (:no_genre_filter OR id IN (
      SELECT mix_id FROM mix_genres mg JOIN genres g ON g.id = mg.genre_id
      WHERE g.slug = ANY(:genres)
  ))
ORDER BY ABS(energy - :energy) + (RANDOM() * 0.3)
LIMIT :limit OFFSET :offset;
```

For 3 sliders active (full vector search):
```sql
SELECT SETSEED(:seed);
SELECT * FROM mixes
WHERE unavailable_at IS NULL
ORDER BY mood_vector <=> cast(:query_vector as vector) + (RANDOM() * 0.05)
LIMIT :limit OFFSET :offset;
```
(Small random jitter added to vector distance so equally-close mixes shuffle.)

---

## Part 3: REST API Endpoints

```
GET  /api/genres
     → returns all genres (for populating the filter chips)

GET  /api/mixes/search?mood=0.3&energy=-0.5&instrumentation=-0.2&genres=jazz,lo-fi&instrumental=true&seed=0.42&limit=20&offset=0
     → each slider param is optional (only sent if that slider is active)
     → 0 sliders: random browse. 1-2 sliders: range filter + random. 3 sliders: pgvector cosine similarity.
     → seed: session-stable random seed for consistent pagination
     → instrumental=true filters to has_vocals = false
     → instrumental=false (default) returns all mixes regardless of vocal content
     → paginated: frontend uses infinite scroll, fetching next batch of 20 via offset

POST /api/mixes/ai-search
     body: { "query": "rainy day coffee shop vibes" }
     → sends query to LLM → gets mood vector → same pgvector search
     → returns mixes + the inferred slider values + inferred genres (so frontend can update sliders and chips)

GET  /api/mixes/{id}
     → single mix details

POST /api/mixes/{id}/report-unavailable
     → marks mix as status = 'unavailable', excluded from future searches

POST /api/mixes/{id}/feedback
     body: { "mood_delta": -0.2, "energy_delta": 0.1 }
     → user feedback to refine classification (future)

GET  /api/health
     → returns app status, DB connectivity, last crawler/classifier run timestamps

--- Admin endpoints (protected by API key via FastAPI Depends()) ---

POST /api/admin/crawl/trigger
     → manually trigger a crawl run

GET  /api/admin/pipeline/status
     → last run times, mixes crawled/classified today, quota usage

POST /api/admin/channels
     body: { "channelId": "UC...", "channelName": "Lofi Girl" }
     → add a new seed channel
```

---

## Part 3b: Python / FastAPI Patterns

### API key authentication — FastAPI `Depends()`
- Public endpoints: `/api/mixes/**`, `/api/genres`, `/api/health`
- Protected endpoints: `/api/admin/**` — require `X-API-Key` header
- Custom dependency function that validates the key from env vars
- Shows: FastAPI dependency injection, middleware patterns, security

### Global exception handling
- Custom exception classes (e.g., `MixNotFoundException`, `ClassificationError`, `RateLimitExceeded`)
- FastAPI `@app.exception_handler()` for consistent error responses
- Response format: `{ "error": "...", "status": 404, "timestamp": "..." }`
- Shows: Python exception hierarchy, FastAPI error handling, proper HTTP status codes

### Rate limiting — slowapi
- Per-IP rate limiting on AI search endpoint (5 req/min)
- Implemented via `slowapi` (wraps the `limits` library, integrates with FastAPI)
- Returns `429 Too Many Requests` with `Retry-After` header
- Shows: middleware pattern, third-party library integration

### Async patterns
- All DB queries via `sqlalchemy[asyncio]` + `asyncpg`
- All external API calls (YouTube, LLM) via `httpx.AsyncClient`
- Celery workers for background pipeline jobs (crawl, classify, analytics) — runs as separate processes
- Shows: Python async/await, async context managers, concurrent I/O, distributed task processing

### Testing — pytest
- **Unit tests**: `classifier_service.py` (mock LLM response → verify vector output), `mix_service.py` (business logic)
- **Integration tests**: search endpoint via `httpx.AsyncClient` + `pytest-asyncio` — test search with various slider/genre/instrumental combos, pagination, error cases
- **DB tests**: test pgvector queries return correct ordering with a test database
- Shows: pytest fixtures, async testing, mocking with `unittest.mock` / `pytest-mock`, test isolation

### Configuration — pydantic-settings
- `Settings` class with typed fields, loaded from `.env` file or environment variables
- Separate settings for dev / prod via env var overrides
- Validated at startup — app fails fast if config is missing
- Shows: pydantic validation, 12-factor app config, type safety

---

## Part 4: Frontend — React SPA (Vite + TypeScript)

### Layout

**Desktop:**
```
┌──────────────────────────────────────────────────────────────┐
│ 🌧️ ──●── ☀️ | 🛋️ ──●── ⚡ | 🥁 ──●── 💻 | (🎤) | Genres▼ | 🔍 │  ← Navbar (~80px)
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  thumb   │  │  thumb   │  │  thumb   │  │  thumb   │   │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤   │
│  │ Title    │  │ Title    │  │ Title    │  │ Title    │   │
│  │ Channel  │  │ Channel  │  │ Channel  │  │ Channel  │   │
│  │ ▬ ▬ ▬    │  │ ▬ ▬ ▬    │  │ ▬ ▬ ▬    │  │ ▬ ▬ ▬    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                          ...                                │
├──────────────────────────────────────────────────────────────┤
│ [thumb] Title - Channel     ◀◀  ▶/⏸  ▶▶    ───●──── 42:15  │  ← Player bar (~70px)
└──────────────────────────────────────────────────────────────┘
```

**Mobile:**
```
┌──────────────────────────────┐
│ 🎵 MoodMix    [🎛️ Filters] [🔍] │  ← Navbar (compact)
├──────────────────────────────┤
│  ┌──────────────────────────┐│
│  │  thumb                   ││
│  ├──────────────────────────┤│
│  │ Title / Channel / ▬ ▬ ▬  ││
│  └──────────────────────────┘│
│            ...               │
├──────────────────────────────┤
│ [thumb] Title    ▶/⏸        │  ← Player bar
│ ──────●───────────── 42:15   │
└──────────────────────────────┘
```

### Navbar (desktop ~80px, single row)
- 3 compact mood sliders with icon labels (🌧️/☀️, 🛋️/⚡, 🥁/💻) — hover shows text ("Sad"/"Happy")
- Vocal toggle: 🎤 icon button (highlighted = instrumental only, dimmed = all)
- Genre dropdown: click opens a panel with 14 toggleable chips, shows selected count
- AI search bar: compact input with 🔍, expands on focus
- Debounced search on any change (~300ms)
- AI search syncs sliders + genre chips to inferred values

### Navbar (mobile — collapsed)
- Logo + "Filters" button (opens slide-down sheet with sliders + genres + vocal toggle) + 🔍 button (opens search bar)
- Maximum screen space for the grid

### Results grid
- Responsive: 1 col (mobile) / 2 cols (tablet) / 3 cols (desktop) / 4 cols (large)
- Each card shows: thumbnail, title, channel, 3 mood bars (color-coded gradients), genre badges
- Subtle background tint derived from the mix's mood values
- Click a card → starts playback in the bottom player bar
- Currently playing card gets visual indicator (accent border / "Now Playing" badge)

### Player bar (bottom, persistent ~70px)
- Spotify-style fixed bottom bar
- Shows: small thumbnail, title + channel, play/pause, prev/next (desktop), progress bar (seekable), elapsed/total time
- Hidden until first mix is played (slide-up animation)
- **Key UX feature:** user can search/filter freely while music keeps playing — the playing mix persists in the bar even if it's no longer in the grid results
- When video ends → auto-play next mix from current search results
- Previous/Next navigate through current search results

### YouTube embed notes
- Premium users get ad-free playback automatically (browser cookies, no OAuth needed)
- Adblockers generally work on embeds (network-level blocking applies inside cross-origin iframes)
- Filter out non-embeddable videos during crawling (`status.embeddable` from YouTube Data API)
- No hover preview available from YouTube IFrame API — static thumbnails only

### Dead/unavailable video handling
Two complementary strategies:

**Proactive: periodic availability check (backend)**
- Scheduled job checks a batch of mixes daily via `videos.list` (1 unit per 50 videos)
- Videos that are deleted, private, or copyright-striked → mark as `status = 'unavailable'`
- Unavailable mixes are excluded from all search results
- Pipeline queues replacement mixes for those regions of the mood space

**Reactive: user-triggered detection (frontend)**
- If YouTube IFrame fires an error (video unavailable, embedding disabled, etc.)
- Show toast notification: "This mix is no longer available, skipping..."
- Gray out the card in the grid if still visible
- Auto-skip to next mix in results
- Send `POST /api/mixes/{id}/report-unavailable` to mark it in DB immediately
- Excluded from subsequent searches for all users

---

## Part 5: UX Decisions

### No landing page — straight to the platform
The app is free and self-explanatory. Let users play music within seconds. A landing page can be added later for SEO if needed.

### Default state on load
- Mood slider auto-enabled and set to time of day (bright in the morning, dark at night)
- Energy and instrumentation sliders off by default
- Mixes already loaded immediately — no empty state, no "start searching" prompt
- User sees time-appropriate mixes and can play within 2 seconds, then tweak sliders from there
- App feels personalized from the first second with zero setup

### Auto time-of-day mood (frontend only, no backend involvement)
- Mood slider follows a smooth sine curve mapped to local time: peaks bright at noon, troughs dark at midnight
- Small clock icon (🕐) toggle next to the mood slider indicates auto-mode is active
- User can grab the slider to override — this disables auto-mode
- Clicking the clock icon re-enables auto-mode
- Preference (auto on/off) persisted in localStorage

### No accounts (v1)
- Zero friction: arrive → listen. No signup wall.
- Use `localStorage` to persist last slider positions + selected genres across sessions
- Accounts can be added later (optional, for saved preferences/history) without architecture changes

### CORS
- FastAPI `CORSMiddleware` with allowed origins for the frontend domain
- Standard setup, configure per environment (localhost for dev, production domain for prod)

### Rate limiting on AI search
- AI search bar calls an LLM API per request — must be rate limited
- Simple approach: per-IP rate limit (e.g., 5 AI searches/minute) via slowapi
- Slider-based search (no LLM call) does not need rate limiting — it's just a DB query

### Infinite scroll
- Initial load: 20 mixes
- As user scrolls near bottom, fetch next 20 via `offset` param
- Slider/genre changes reset the scroll and reload from offset 0

### Responsive grid
- Mobile: 1 card per row
- Tablet: 2 cards per row
- Desktop: 3 cards per row
- Large desktop: 4 cards per row
- CSS grid with `auto-fill` / media queries

---

## Part 6: Implementation Order

### Phase 1 — FastAPI foundation
1. Initialize project with `uv` or `poetry`, install dependencies
2. FastAPI app scaffold (`main.py`, `config.py`, `database.py`)
3. pydantic-settings for typed config + `.env` files
4. SQLAlchemy async engine + Alembic migration (mixes, genres, mix_genres, seed_channels tables)
5. Custom exception classes + global exception handlers
6. SQLAlchemy models (`Mix`, `Genre`, `SeedChannel`)

### Phase 2 — Data Pipeline
7. `crawler_service.py` — channel crawl + keyword search via `httpx`
8. Export crawled mixes as JSON → classify initial seed via Claude Code (batches of ~50-100)
9. Import classified results into PostgreSQL
10. `classifier_service.py` — automated LLM classification (Haiku or OSS GPT-120B) for ongoing new mixes

### Phase 3 — API layer
12. `mixes` router — search endpoint (sliders + genres + instrumental filter + pagination)
13. `ai_search_service.py` + endpoint — natural language → mood vector
14. API key dependency for `/api/admin/**` endpoints
15. `admin` router — trigger crawl, pipeline status, manage seed channels
16. Rate limiting (slowapi) on AI search endpoint
17. `/api/health` endpoint

### Phase 4 — Testing
18. Unit tests: `classifier_service.py`, `mix_service.py`
19. Integration tests: search endpoint via `httpx.AsyncClient` (search combos, pagination, error cases)
20. DB tests: verify pgvector query ordering

### Phase 5 — Frontend MVP
21. Vite + React + TypeScript app scaffold
22. 3 sliders + genre chips + vocal toggle + results grid connected to FastAPI
23. YouTube embed player + dead video handling
24. AI search bar + slider/chip sync
25. Infinite scroll + localStorage persistence

### Phase 6 — Deployment
26. Dockerfile + docker-compose
27. GitHub Actions CI/CD pipeline
28. nginx reverse proxy + SSL on VPS

### Phase 7 — Redis caching
29. Add Redis to docker-compose
30. Cache search results — key = hash of (mood, energy, instrumentation, genres, instrumental, offset), TTL ~30-60s
31. Cache genre list (`GET /api/genres`) — rarely changes, TTL ~1 hour
32. Invalidate relevant caches when new mixes are classified or mixes are marked unavailable

### Phase 8 — Celery task queue
33. Replace APScheduler with Celery + Redis as broker
34. Celery tasks: `crawl_channels`, `crawl_keywords`, `classify_pending_mixes`, `check_availability`
35. Celery Beat for scheduling (weekly channel crawl, daily keyword search, daily availability check)
36. Docker-compose becomes: FastAPI + Celery worker + Celery Beat + Redis
37. Shows production-grade async task architecture

### Phase 9 — Catalog analytics (pandas)
38. `analytics_service.py` — scheduled job (Celery task) that generates catalog health reports
39. Mood space coverage: divide 3D space into regions, count mixes per region, identify gaps
40. Genre distribution: mix count per genre, underrepresented genres
41. Confidence score distribution: histogram of classification confidence, flag low-confidence clusters
42. Gap detection: recommend crawler search queries to fill sparse mood regions
43. Expose via `GET /api/admin/analytics` (protected) — returns latest report as JSON
44. Data processing uses pandas DataFrames for aggregation, groupby, pivot tables

### Phase 10 — MCP server
45. MCP server exposing catalog tools for AI agents (Claude Desktop, Claude Code, etc.)
46. Read tools: `search_mixes`, `get_mix_stats`, `get_catalog_analytics`, `get_low_confidence_mixes`
47. Write tools: `add_seed_channel`, `trigger_crawl`, `update_mix_classification`
48. Connects to the same PostgreSQL DB and reuses existing service logic
49. Separate entrypoint (can run alongside or independently of the FastAPI server)

### Phase 11 — Refinement (future)
50. User feedback loop
51. UI polish, responsive mobile layout
52. Optional: accounts for saved preferences/history

---

## Deployment

### Backend: Docker + GitHub Actions → Hetzner VPS
- `backend/Dockerfile` — multi-stage build (builder: compile asyncpg C extensions with uv → runtime: slim image with non-root user)
- `backend/Dockerfile.test` — standalone single-stage build with dev deps, runs migrations + pytest
- GitHub Actions pipeline:
  - `test.yml`: on push/PR to `main` (path-filtered to `backend/**`) → runs tests in Docker via `docker compose -f docker-compose.test.yml run --rm --build test`
  - `deploy.yml`: triggers via `workflow_run` after tests pass → SSH to VPS via `appleboy/ssh-action` → `command=` restriction runs `deploy.sh`
- `deploy.sh` on VPS: `git pull` → backup current image → build new image → run migrations in temp container → bring up new version (rollback on migration failure)
- Docker Compose on VPS (`docker-compose.prod.yml`):
  - `db` — pgvector/pgvector:pg17 (healthcheck, persistent volume)
  - `api` — FastAPI + uvicorn, bound to `127.0.0.1:8000`
- Environment variables (DB password, API keys) via `.env` / `.env.prod` files on VPS, not in repo
- VPS user `moodmix` with restricted sudoers (docker commands only) + SSH `command=` restriction

### Frontend: Cloudflare Pages
- `vite build` → deployed to Cloudflare Pages
- Production `VITE_API_URL` points to `https://api.moodmix.fm`

### HTTPS + nginx
- Cloudflare DNS proxy (A record `api` → VPS IP) handles public SSL
- nginx reverse proxy on VPS: `api.moodmix.fm` → `127.0.0.1:8000`
- Self-signed cert on VPS for Cloudflare Full SSL mode
- Admin panel (`/admin/`) protected with sqladmin auth + Cloudflare WAF rate limiting on `/admin/login`

### Logging & monitoring
- Python `logging` module with structured output for crawler/classifier job status
- `GET /api/health` endpoint — returns app status, DB connectivity, catalog size
- Docker logs accessible via `docker compose logs`

---

## Monthly Cost Estimate

| Component | Cost |
|-----------|------|
| PostgreSQL (self-hosted in Docker) | $0 |
| YouTube Data API | Free (within 10K/day) |
| LLM classification (Haiku or OSS GPT-120B) | ~$0-0.10/mo |
| VPS (Hetzner — already owned, 2 vCPU / 4GB) | Already paid |
| Frontend hosting (Cloudflare Pages) | Free tier |
| Domain (moodmix.fm) | ~$10/yr |
| **Total** | **~$0/mo** |

---

## Verification Plan

1. **FastAPI**: App starts, connects to PostgreSQL, Alembic migration runs successfully
2. **Crawler**: Run on 5 seed channels → verify mixes appear in DB with correct metadata
3. **Classifier**: Classify 50 mixes → manually spot-check 10 for reasonable vector values
4. **API**: `GET /api/mixes/search?mood=-1&energy=-1&instrumentation=-1` returns dark/chill/organic mixes
5. **AI search**: `POST /api/mixes/ai-search` with "upbeat electronic focus music" → plausible results
6. **Frontend**: Sliders move → results update → click → YouTube embed plays
7. **CI/CD**: Push to `main` → tests pass → deploy triggers → new version live on VPS
8. **Health**: `GET /api/health` returns healthy response with DB connectivity and catalog size
