# Search Logic

How the mix search engine works under the hood.

## Overview

The search adapts its strategy based on how many sliders the user has active. Each slider (mood, energy, instrumentation) can be toggled on or off. The fewer sliders active, the broader the results.

## Search strategies

### 0 sliders — Random browse
No mood filtering at all. Returns random mixes from the catalog, seeded for stable pagination (same session = same order).

### 1-2 sliders — Range filter + weighted random
For each active slider:
1. Filter to mixes within **±0.25** of the target value (range)
2. Sort by **Manhattan distance** from target + random jitter

Example: mood=-0.5 → only mixes with mood between -0.75 and -0.25, sorted by how close they are to -0.5.

Inactive sliders are completely ignored — no filtering or sorting on those axes.

### 3 sliders — pgvector cosine similarity
Uses the 3D mood vector `[mood, energy, instrumentation]` and PostgreSQL's pgvector `<=>` operator to find the closest mixes in vector space. This is the most precise search mode.

## Random jitter

All strategies add a small random factor (`0.3`) to the distance score. This prevents identical results on every search — mixes of similar relevance shuffle each time, while clearly closer mixes still rank higher.

## Session-stable pagination (SETSEED)

The frontend generates a random seed per session (e.g., `0.42`). This seed is sent with every request. PostgreSQL's `SETSEED()` ensures `RANDOM()` produces the same sequence for the same seed — so page 2 continues where page 1 left off. New session = new seed = fresh shuffle.

## Channel diversity cap

Without diversity control, channels with hundreds of mixes (e.g., Anjunadeep) dominate results. The service fetches up to 500 candidate mixes sorted by relevance, then applies a **max 4 per channel** filter in Python before paginating.

This means:
- Any page of 20 results has at most 4 mixes from the same channel
- Each page independently applies the cap — so channel X can appear on both page 1 and page 2
- Results are still sorted by relevance within the diversity constraint

## Genre and vocal filters

- **Genre filter**: subquery join on `mix_genres` → `genres` — only mixes tagged with at least one of the selected genres
- **Instrumental toggle**: `WHERE has_vocals = false` — excludes vocal mixes
- Both combine with slider filters via `AND` clauses

## Base filters (always applied)

- `unavailable_at IS NULL` — exclude dead/removed YouTube videos
- `mood IS NOT NULL` — only show classified mixes (unclassified ones haven't been reviewed yet)
