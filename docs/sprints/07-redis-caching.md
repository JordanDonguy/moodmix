# Sprint 7 — Redis Caching

**Goal:** Cache frequent queries to reduce DB load and improve response times.

**Depends on:** Sprint 6 (Redis running in docker-compose)

## Tasks

### 7.1 — Redis client setup
- [ ] Add `redis` (async) to dependencies
- [ ] `app/cache.py` — async Redis client, initialized from `settings.REDIS_URL`
- [ ] Add `REDIS_URL` to config (default: `redis://localhost:6379`)
- [ ] Connect/disconnect in FastAPI lifespan handler

### 7.2 — Search result caching
- [ ] Cache key = hash of all search params: `search:{hash(valence, energy, instrumentation, genres, instrumental, limit, offset)}`
- [ ] TTL: 30-60 seconds
- [ ] On cache hit: return cached JSON directly (skip DB query)
- [ ] On cache miss: query DB, serialize response, store in Redis, return
- [ ] Implement as a utility function or decorator on the service method

### 7.3 — Genre list caching
- [ ] Cache key: `genres:all`
- [ ] TTL: 1 hour (genres rarely change)
- [ ] Invalidate on genre add/modify (if ever needed)

### 7.4 — Cache invalidation
- [ ] When a mix is classified (new mixes enter search results): flush all `search:*` keys
- [ ] When a mix is marked unavailable: flush all `search:*` keys
- [ ] Simple approach: `redis.delete()` with pattern matching or just flush all search keys
- [ ] Pipeline runs that modify catalog should trigger invalidation

### 7.5 — Health check update
- [ ] Add `redis_connected: bool` to `/api/health` response
- [ ] Ping Redis in health check

## Done when

- [ ] First search request: normal response time (~50-100ms)
- [ ] Second identical request: faster response time (~5-10ms, cache hit)
- [ ] After a mix is classified or marked unavailable: cache is cleared, next request hits DB
- [ ] `/api/health` reports Redis status
