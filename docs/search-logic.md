# Search Logic

How the mix search engine works under the hood.

## Overview

The search adapts its strategy based on how many sliders the user has active. Each slider (mood, energy, instrumentation) can be toggled on or off. The fewer sliders active, the broader the results.

The algorithm flows through five stages:

```
count active sliders → collect candidates → interleave by channel → paginate → hydrate
```

## Search strategies

### 0 sliders — Random browse
No mood filtering at all. Returns random mixes from the catalog, seeded for stable pagination (same session = same order).

### 1-2 sliders — Range filter + weighted random
For each active slider:
1. Filter to mixes within a **tolerance range** of the target value
2. Sort by **Manhattan distance** (sum of absolute differences) from target + random jitter

Example: mood=-0.5 with tolerance 0.25 → only mixes with mood between -0.75 and -0.25, sorted by how close they are to -0.5.

Inactive sliders are completely ignored — no filtering or sorting on those axes.

**Tolerance widening**: if the initial ±0.25 range doesn't produce enough results to fill the requested page, the search automatically retries with ±0.5, then ±0.8. This prevents empty pages when sliders are set to sparse regions of the catalog. Candidates from narrower tolerances keep their relevance ranking — wider attempts only add new, lower-relevance matches.

### 3 sliders — pgvector L2 distance
Uses the 3D mood vector `[mood, energy, instrumentation]` and PostgreSQL's pgvector `<->` operator (L2/Euclidean distance) to find the closest mixes in vector space. This is the most precise search mode.

No tolerance widening needed here — L2 distance is a ranking score, not a hard filter. The search fetches a bounded candidate pool (top K by distance) and paginates within that pool.

## Random jitter

All strategies add a small random factor (`0.3`) to the distance score. This prevents identical results on every search — mixes of similar relevance shuffle each time, while clearly closer mixes still rank higher.

## Session-stable pagination (SETSEED)

The frontend generates a random seed per session (e.g., `0.42`). This seed is sent with every request. PostgreSQL's `SETSEED()` ensures `RANDOM()` produces the same sequence for the same seed — so page 2 continues where page 1 left off. New session = new seed = fresh shuffle.

The seed is re-applied before each query attempt (including tolerance widening retries) so the jitter sequence stays deterministic regardless of how many attempts are needed.

## Channel diversity — Round-robin interleaving

Without diversity control, channels with hundreds of mixes (e.g., Anjunadeep) dominate results. After collecting candidates in relevance order, the service interleaves them by channel using a round-robin algorithm:

1. Group candidates by channel, preserving relevance order within each group
2. Take the top-ranked mix from each channel, then the second-ranked from each, and so on

Example:
```
Relevance order:  [A1, A2, A3, B1, A4, C1]
After interleave: [A1, B1, C1, A2, A3, A4]
```

This is fully deterministic (no randomness), so pagination stays stable. It maximizes channel spread at the top of results while preserving within-channel relevance ordering. No arbitrary per-channel caps needed.

## Candidate pool sizing

The search over-fetches candidates to ensure the channel interleaving step has enough material to fill any requested page:

```
pool_size = max(500, (offset + limit) * 5)
```

This scales with pagination depth — deeper pages trigger larger candidate pools so the interleave can still produce diverse results even when one channel dominates the relevance ranking.

## Pagination

The frontend uses infinite scroll with cursor-based "did we get a full page?" detection:

```ts
getNextPageParam: (lastPage) =>
    lastPage.mixes.length === PAGE_SIZE ? nextOffset : undefined
```

No total count is needed — pagination ends when the backend returns fewer mixes than requested, meaning the candidate pool is exhausted.

## Genre and vocal filters

- **Genre filter**: subquery join on `mix_genres` → `genres` — only mixes tagged with at least one of the selected genres
- **Instrumental toggle**: `WHERE has_vocals = false` — excludes vocal mixes
- Both combine with slider filters via `AND` clauses

## Base filters (always applied)

- `unavailable_at IS NULL` — exclude dead/removed YouTube videos
- `mood IS NOT NULL` — only show classified mixes (unclassified ones haven't been reviewed yet)
