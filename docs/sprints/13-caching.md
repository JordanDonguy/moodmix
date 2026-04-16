# Sprint 13 — Caching (Redis)

**Goal:** Cache hot search queries and reference data to reduce DB load.

**Depends on:** Sprint 11 (Redis already in infra) + Sprint 10 (analytics shows what's actually hot)

**Trigger:** Defer until measured. Don't ship this until either (a) p95 search latency degrades, or (b) analytics shows specific query patterns hammering the DB. Redis caching is the classic premature-optimization trap.

## Scope

- Cache layer for `/mixes/search` keyed by hashed query params
- Cache layer for `/genres` (rarely changes, cheap to invalidate)
- TTL strategy: short for searches (10-15 min), long for genres (1 day)
- Invalidation on mix updates (admin edits, crawl additions, classification updates)
- Cache hit/miss metrics surfaced in admin dashboard

## Out of scope

- Per-user caching of personalized results (premature)
- Fragment caching at the API response level (too coarse)

## Decisions to make during impl

- Cache key format — pure hash vs human-readable
- Invalidation strategy — broad (clear-all on any mix change) vs targeted (only invalidate keys touching the changed mix). Probably broad to start
- Should anonymous and authenticated requests share cache? Yes for now

## Done when

- Cache hit rate > 50% on `/mixes/search`
- No stale data after admin edits (verify with a test)
- Hit/miss rate visible in admin dashboard
