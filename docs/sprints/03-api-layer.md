# Sprint 3 — API Layer

**Goal:** All REST endpoints functional and tested manually via Swagger UI.

**Depends on:** Sprint 2 (classified mixes in DB)

## Tasks

### 3.1 — Pydantic schemas
- [x] `app/schemas/mix.py`
  - `MixResponse` — what the frontend receives per mix (id, youtube_id, title, channel_name, thumbnail_url, duration_seconds, mood, energy, instrumentation, has_vocals, genres list)
  - `MixSearchResponse` — `{ mixes: list[MixResponse], total: int, limit: int, offset: int }`
- [x] `app/schemas/genre.py`
  - `GenreResponse` — id, name, slug
- [x] `app/schemas/search.py`
  - `AiSearchRequest` — `{ query: str }`
  - `AiSearchResponse` — extends MixSearchResponse + `inferred` object (mood, energy, instrumentation, genres, instrumental)
- [x] `app/schemas/admin.py`
  - `TriggerCrawlRequest` — `{ type: str }` (channel_crawl | keyword_search | availability_check)
  - `AddChannelRequest` — `{ channel_id: str, channel_name: str }`
  - `UpdateChannelRequest` — `{ active: bool }`
  - `ChannelResponse`, `PipelineStatusResponse`
- [x] `app/schemas/common.py`
  - `ErrorResponse` — `{ error: str, status: int, timestamp: str }`

> **Pattern: Interface Segregation (via DTOs)** — Each consumer gets a tailored schema. The frontend sees `MixResponse` (no description, no tags, no internal fields). Admin sees `PipelineStatusResponse`. DB models are never exposed directly — Pydantic schemas are the API contract.

**Files created:**
```
app/schemas/
├── __init__.py
├── mix.py
├── genre.py
├── search.py
├── admin.py
└── common.py
```

### 3.2 — Mix service
- [x] `app/services/mix_service.py`
- [x] `search_mixes(session, mood, energy, instrumentation, genres, instrumental, limit, offset)` — pgvector cosine similarity query with filters
- [x] `get_mix_by_id(session, mix_id)` — single mix lookup
- [x] `report_unavailable(session, mix_id)` — set unavailable_at, nullify mood_vector so it drops from search
- [x] Test query manually: verify results are ordered by mood similarity

> **Pattern: Repository-like service layer** — `MixService` encapsulates all DB query logic. Routers never write SQL or touch SQLAlchemy directly — they call service methods. This keeps routers thin (just HTTP concerns: parse params, call service, return response) and services testable independently.

### 3.3 — Genres router
- [x] `app/routers/genres.py`
- [x] `GET /api/genres` — return all genres
- [x] Test via Swagger UI

### 3.4 — Mixes router
- [x] `app/routers/mixes.py`
- [x] `GET /api/mixes/search` — query params: mood, energy, instrumentation, genres (comma-sep), instrumental (bool), limit, offset
  - Validate ranges (-1 to 1 for mood params, 1-50 for limit)
  - Call `mix_service.search_mixes()`
  - Return `MixSearchResponse`
- [x] `GET /api/mixes/{id}` — single mix
- [x] `POST /api/mixes/{id}/report-unavailable` — mark unavailable
- [x] Test all via Swagger UI with various param combos

### 3.5 — AI search service + endpoint
- [ ] `app/services/ai_search_service.py`
- [ ] `parse_natural_language(query: str) -> InferredSearch` — sends query to LLM, returns mood vector + optional genres + instrumental flag
- [ ] Prompt: "Convert this into mood values (mood -1 to 1, energy -1 to 1, instrumentation -1 to 1) and optionally genres from this list: [...]. Respond as JSON."
- [ ] `POST /api/mixes/ai-search` in mixes router — calls AI search service, then mix_service.search_mixes(), returns results + inferred values
- [ ] Test: "rainy day coffee shop vibes" → expect negative energy, jazz/lo-fi genres

> **Pattern: Strategy (reuse)** — `AiSearchService` can reuse the same `ClassifierStrategy` protocol from sprint 2 for the LLM call, since it's the same type of operation (send text to LLM, get structured JSON back). Or a simpler dedicated LLM client — depends on how different the prompts are. Either way, the LLM provider is injected, not hardcoded.

### 3.6 — Admin auth middleware
- [ ] `app/middleware/auth.py`
- [ ] `verify_api_key` dependency: reads `X-API-Key` header, compares to `settings.ADMIN_API_KEY`
- [ ] Returns 401 with error response if missing/invalid
- [ ] Apply to all `/api/admin/**` routes via router-level `dependencies=[Depends(verify_api_key)]`

> **Pattern: Dependency Injection** — Auth is a FastAPI dependency, not a decorator or manual check in each endpoint. Applied once at the router level, automatically protects all admin routes. Easy to test (override dependency in tests).

### 3.7 — Admin router
- [ ] `app/routers/admin.py`
- [ ] `POST /api/admin/crawl/trigger` — enqueue crawl task (for now, run synchronously; Celery in sprint 8)
- [ ] `GET /api/admin/pipeline/status` — query `pipeline_runs` for latest run per type + today's totals
- [ ] `POST /api/admin/channels` — add seed channel (409 if duplicate)
- [ ] `GET /api/admin/channels` — list all seed channels
- [ ] `PATCH /api/admin/channels/{id}` — activate/deactivate
- [ ] All protected by `verify_api_key` dependency
- [ ] Test via Swagger UI with API key header

### 3.8 — Rate limiting
- [ ] `app/middleware/rate_limit.py`
- [ ] Install + configure `slowapi`
- [ ] Apply to `POST /api/mixes/ai-search` only: 5 req/min per IP
- [ ] Return 429 with `Retry-After` header
- [ ] Test: hit endpoint 6 times rapidly → 6th should return 429

### 3.9 — Health endpoint enhancement
- [ ] Update `GET /api/health` to return:
  - DB connectivity (try a simple query)
  - Last crawl/classification timestamps (from pipeline_runs)
  - Catalog size (count of classified mixes)

**Files created:**
```
app/services/mix_service.py
app/services/ai_search_service.py
app/middleware/auth.py
app/middleware/rate_limit.py
app/routers/genres.py
app/routers/mixes.py
app/routers/admin.py
```

## Done when

- [ ] All endpoints visible in Swagger UI at `/docs`
- [ ] `GET /api/genres` returns 14 genres
- [ ] `GET /api/mixes/search?mood=-1&energy=-1&instrumentation=-1` returns dark/chill/organic mixes
- [ ] `POST /api/mixes/ai-search` with "upbeat electronic" returns relevant results + inferred slider values
- [ ] Admin endpoints return 401 without API key, 200 with correct key
- [ ] Rate limiter blocks 6th AI search request within a minute
- [ ] `POST /api/mixes/{id}/report-unavailable` marks mix, excluded from subsequent searches
