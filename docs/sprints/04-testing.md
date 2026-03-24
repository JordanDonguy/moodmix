# Sprint 4 — Testing

**Goal:** Solid test coverage on critical paths. Recruiter-visible test suite.

**Depends on:** Sprint 3 (all endpoints working)

## Tasks

### 4.1 — Test infrastructure
- [ ] Add dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (for async test client)
- [ ] `tests/conftest.py` — shared fixtures:
  - `test_db` — async session connected to the local Docker Postgres (same `docker-compose.dev.yml`, separate test database or transaction rollback)
  - `async_client` — `httpx.AsyncClient` pointed at the FastAPI app (using `ASGITransport`)
  - `seeded_db` — fixture that inserts a few test mixes + genres for search tests
  - `admin_headers` — `{ "X-API-Key": test_api_key }`
  - Override `get_db` dependency to inject `test_db` session
  - Override `ClassifierStrategy` dependency with a mock implementation

> **Pattern: Dependency Injection payoff** — All the DI setup from sprints 1-3 pays off here. To test a router without hitting a real LLM, just override `Depends(get_classifier)` with a mock. To test without touching the real DB, override `Depends(get_db)`. No monkey-patching needed — FastAPI's `app.dependency_overrides` makes this clean.

**Files created:**
```
tests/
├── conftest.py
└── __init__.py
```

### 4.2 — Unit tests: classifier service
- [ ] `tests/test_classifier.py`
- [ ] Test cases:
  - Mock LLM response with valid JSON → verify parsed mood vector, genres, has_vocals
  - Mock LLM response with out-of-range values → verify clamping to [-1, 1]
  - Mock LLM response with unknown genre slug → verify it's ignored (only known slugs accepted)
  - Mock LLM returning invalid JSON → verify graceful error handling
  - Mock LLM timeout → verify retry logic

### 4.3 — Unit tests: mix service
- [ ] `tests/test_mix_service.py`
- [ ] Test cases:
  - Search with neutral vector [0,0,0] → returns results ordered by similarity
  - Search with genre filter → only matching genres returned
  - Search with instrumental=true → only has_vocals=false mixes
  - Search with offset/limit → correct pagination
  - Report unavailable → mix excluded from subsequent search

### 4.4 — Integration tests: search endpoint
- [ ] `tests/test_mixes_router.py`
- [ ] Test via `httpx.AsyncClient` against the actual FastAPI app:
  - `GET /api/mixes/search` with valid params → 200 + correct response shape
  - `GET /api/mixes/search` with out-of-range valence (e.g., 5.0) → 400
  - `GET /api/mixes/search` with genre filter → filtered results
  - `GET /api/mixes/search` with limit=0 → 400
  - `GET /api/mixes/{id}` with valid ID → 200
  - `GET /api/mixes/{id}` with unknown ID → 404 with error format
  - `POST /api/mixes/{id}/report-unavailable` → 200, then search excludes it

### 4.5 — Integration tests: admin endpoints
- [ ] `tests/test_admin_router.py`
- [ ] Test cases:
  - All admin endpoints without API key → 401
  - All admin endpoints with wrong API key → 401
  - `POST /api/admin/channels` with valid data + correct key → 201
  - `POST /api/admin/channels` with duplicate → 409
  - `GET /api/admin/channels` → list includes new channel
  - `PATCH /api/admin/channels/{id}` → active toggled

### 4.6 — Integration tests: AI search
- [ ] `tests/test_ai_search.py`
- [ ] Test cases:
  - Mock LLM API → verify inferred values are returned alongside results
  - Verify slider values in response match what LLM returned
  - Rate limit: 6th request within a minute → 429

### 4.7 — DB tests: pgvector ordering
- [ ] `tests/test_pgvector.py`
- [ ] Insert 5 mixes with known mood vectors
- [ ] Query with a target vector → verify results are ordered by cosine distance
- [ ] Example: query [1, 1, 1], mix with [0.9, 0.9, 0.9] should rank above [-1, -1, -1]

### 4.8 — CI integration
- [ ] Add `pytest` to the CI pipeline (GitHub Actions — created in sprint 6, but prep the test command now)
- [ ] Add `pytest --cov=app --cov-report=term-missing` for coverage reporting
- [ ] Target: >70% coverage on services, >50% overall

**Files created:**
```
tests/
├── conftest.py
├── test_classifier.py
├── test_mix_service.py
├── test_mixes_router.py
├── test_admin_router.py
├── test_ai_search.py
└── test_pgvector.py
```

## Done when

- [ ] `pytest` runs green with all tests passing
- [ ] Coverage report shows >50% overall
- [ ] Key paths covered: search, classification, admin auth, pgvector ordering
- [ ] Tests can run in CI (no hard dependency on external services — LLM calls mocked)
