# Sprint 5 — Testing

**Goal:** Solid test coverage on critical paths. Recruiter-visible test suite.

**Depends on:** Sprint 3 (all endpoints working)

## Tasks

### 4.1 — Test infrastructure
- [x] Add dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (for async test client)
- [x] `tests/conftest.py` — shared fixtures:
  - `db` — async session connected to the test Docker Postgres, wrapped in a rollback transaction
  - `client` — `httpx.AsyncClient` pointed at the FastAPI app (using `ASGITransport`)
  - `seeded_client` — client backed by pre-loaded test data
  - `seeded_db` — fixture that inserts test mixes + genres for search tests
  - `mock_youtube_client` — `AsyncMock(spec=YouTubeClient)` for crawler tests
  - `admin_headers` — per-test fixture that patches `settings.ADMIN_API_KEY`
  - Override `get_db` dependency to inject test session
  - `join_transaction_mode="create_savepoint"` so service `commit()` calls don't break test isolation

> **Pattern: Dependency Injection payoff** — All the DI setup from sprints 1-3 pays off here. To test a router without hitting a real LLM, just override `Depends(get_ai_search_service)` with a mock. To test without touching the real DB, override `Depends(get_db)`. No monkey-patching needed — FastAPI's `app.dependency_overrides` makes this clean.

**Files created:**
```
tests/
├── conftest.py
└── __init__.py
```

### 4.2 — Unit tests: classifier / AI service
- [x] `tests/unit/test_ai_search_service.py`
- [x] Test cases:
  - Mock LLM response with valid JSON → verify parsed mood vector, genres, instrumental
  - Mock LLM response with out-of-range values → verify clamping to [-1, 1]
  - Mock LLM returning invalid JSON → verify graceful fallback to defaults
  - Mock LLM returning empty response → verify retry logic
  - Request payload inspection → verify correct fields sent to LLM

### 4.3 — Unit tests: mix service
- [x] `tests/services/test_mix_service.py`
- [x] Test cases:
  - Search with neutral vector [0,0,0] → returns results ordered by L2 distance
  - Search with genre filter → only matching genres returned
  - Search with instrumental=true → only has_vocals=false mixes
  - Search with offset/limit → correct pagination
  - Tolerance widening → sparse 1-slider query widens range until results found
  - Report unavailable → mix marked with unavailable_at timestamp
  - Get mix by ID → returns mix with genres eager-loaded

### 4.4 — Integration tests: search endpoint
- [x] `tests/routers/test_mixes_router.py`
- [x] Test via `httpx.AsyncClient` against the actual FastAPI app:
  - `GET /api/mixes/search` with valid params → 200 + correct response shape
  - `GET /api/mixes/search` with out-of-range mood (e.g., 5.0) → 422
  - `GET /api/mixes/search` with genre filter → filtered results
  - `GET /api/mixes/search` with limit/offset → values echoed in response envelope
  - `GET /api/mixes/{id}` with valid ID → 200 with correct data
  - `GET /api/mixes/{id}` with unknown ID → 404
  - `GET /api/mixes/not-a-uuid` → 422
  - `POST /api/mixes/{id}/report-unavailable` → 204
  - `POST /api/mixes/ai-search` with mocked LLM → 200 with inferred + mixes
  - `POST /api/mixes/ai-search` with query too short → 422

### 4.5 — Integration tests: admin endpoints
- [x] `tests/routers/test_admin_router.py`
- [x] Test cases:
  - Admin endpoints without API key → 401
  - Admin endpoints with wrong API key → 403
  - `POST /api/admin/channels` with valid data + correct key → 201
  - `POST /api/admin/channels` with duplicate → 409
  - `GET /api/admin/channels` → returns list (empty state)
  - `PATCH /api/admin/channels/{id}` → active toggled to false
  - `PATCH /api/admin/channels/{unknown}` → 404
  - `GET /api/admin/pipeline/status` → 200 with runs + total

### 4.6 — Integration tests: AI search
- [x] Covered in `test_mixes_router.py` (`TestAiSearchEndpoint`) and `test_ai_search_service.py`
- [x] Mock LLM API → verify inferred values are returned alongside results
- [x] Verify response shape includes `inferred` and `mixes` keys

### 4.7 — DB tests: pgvector ordering
- [x] Covered in `tests/services/test_mix_service.py` (`test_three_sliders_orders_by_l2_distance`)
- [x] 3-slider query uses pgvector L2 distance → closest vector ranks first
- [x] Genre subquery join tested against real Postgres + pgvector

### 4.8 — CI integration
- [x] `make test` runs `pytest --cov=app --cov-report=term-missing` via `ENV_FILE=.env.test`
- [x] `docker-compose.test.yml` + `make test-db-up/down/migrate` for isolated test DB
- [x] Coverage: 85% overall, 97–100% on services, 64%+ on youtube_client

**Files created:**
```
tests/
├── conftest.py
├── unit/
│   ├── test_ai_search_service.py
│   ├── test_mix_service_helpers.py
│   └── test_youtube_client.py
├── services/
│   ├── test_mix_service.py
│   ├── test_admin_service.py
│   └── test_crawler_service.py
└── routers/
    ├── test_mixes_router.py
    ├── test_admin_router.py
    ├── test_genres_router.py
    └── test_health_router.py
```

## Done when

- [x] `pytest` runs green with all tests passing (103 tests)
- [x] Coverage report shows >50% overall (85% achieved)
- [x] Key paths covered: search, AI search, admin auth, pgvector ordering, crawler
- [x] Tests can run without external services — YouTube and LLM calls mocked via `httpx.MockTransport`
