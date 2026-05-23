# Sprint 13 — Track Scenes POC

**Goal:** Build an internal experimentation tool to validate the anchor-based playlist generation idea. Given a track to anchor a "vibe," generate a list of similar-but-coherent tracks via embedding similarity, optionally shifted along the mood vector axes (more chill, more dark, more electronic, etc.). The point is not to ship a feature — it's to **answer a set of open questions** about how to build the production playlist engine.

**Depends on:** Sprint 11 (needs populated `embedding` + `mood_vector` columns), Sprint 12 (admin panel shell)

## Open questions the POC must answer

These drive the design of every knob in the tool — each control exists to test one hypothesis.

1. **Single anchor or multiple?** Does a 1-track anchor produce a coherent enough scene, or do we need to average 2-5 anchors to get a stable "center of gravity" for the vibe?
2. **Genre restriction on or off?** Does relying purely on embedding similarity give cross-genre matches that *feel* right, or do we need a genre filter to keep the scene cohesive?
3. **Pool size + shuffle strategy.** Top-50 deterministically might be too repetitive on re-runs. Fetch top-500 and pick 50 at random? Top-200 + weighted random by mood-proximity? What gives variety without losing coherence?
4. **Vocals threshold.** Is `vocals < 0.8` a sensible default for background-music listening, or does cutting all vocal-heavy tracks make the catalog feel impoverished?
5. **How much mood shift breaks coherence?** A small ±0.1 shift should preserve the vibe; ±0.5 probably doesn't. Where's the inflection point?
6. **Does cosine distance on Effnet embeddings actually capture "feels similar"?** Or do we need a different distance metric, a different embedding pooling strategy, or a weighted combo of embedding + mood + genre?

## Scope

### Admin "Scene workbench" view

A single-page admin view dedicated to scene experimentation.

#### Anchor selection

- Search box: type-ahead by title / artist name (across the full classified catalog)
- Result row shows: title, artist, duration, mood vector chip, top genre, vocals score
- Click a result to set it as anchor (or add to a multi-anchor set)
- "Clear anchors" + "Random anchor" buttons for quick iteration

#### Knob panel (above results)

All knobs adjustable live; the result list re-queries on change with a small debounce.

- **Mood shift** — three sliders (mood / energy / instrumentation), each `-1` to `+1`, default `0`. Adds delta to the target mood vector.
- **Vocals max** — slider `0.0` to `1.0`, default `1.0` (no filter). Filters `features.binary.voice_instrumental.voice < threshold`.
- **Genre filter** — multi-select dropdown of top Discogs styles (populated from existing track distribution). Optional; off by default.
- **Pool size** — input or stepper for `N` (the size of the candidate pool fetched before shuffle/rank). Suggested defaults: 50, 100, 200, 500.
- **Result count** — number of tracks to return after pool selection (default 50).
- **Shuffle strategy** — radio: `top-N deterministic` / `pure random from pool` / `weighted random by mood-distance` / `top-K shuffled` (K configurable).
- **Anchor mode** — radio: `single anchor` / `centroid of all anchors` / `closest-to-any` (each candidate's distance = min distance to any anchor).

#### Results panel

- Ranked list of candidate tracks with: title, artist, mood vector chip, vocals score, embedding distance to anchor, mood-target distance
- Each row has an inline **SoundCloud embed player** (one widget per row, lazy-loaded so the page isn't immediately heavy)
- "Play all" mode that auto-advances through the list (helps audition flow, not just individual tracks)
- "Mark good / mark bad" buttons per track — local-only tags for the current session, exported with the snapshot

#### Snapshot export

Each scene configuration + result list is exportable as a JSON snapshot for offline review and comparison across runs:

- Anchor track IDs, all knob values, result list with distances + manual labels
- Saved to `backend/data/scene_snapshots/{timestamp}.json`
- Reviewing these side-by-side answers most of the open questions above without needing a long-running A/B test infrastructure

### Backend endpoint

#### `POST /admin/scenes/preview`

Single endpoint that takes the full knob state and returns the ranked candidate list. Body roughly:

```json
{
  "anchor_track_ids": ["uuid", ...],
  "anchor_mode": "single" | "centroid" | "closest-to-any",
  "mood_shift": {"mood": 0.0, "energy": 0.0, "instrumentation": 0.0},
  "vocals_max": 1.0,
  "genres": [],
  "pool_size": 200,
  "result_count": 50,
  "shuffle_strategy": "weighted_random" | "top_n" | "random_from_pool" | "top_k_shuffled",
  "shuffle_k": 100
}
```

Response: ranked list with track + distances + features summary.

Backed by a small `SceneQueryService` (`app/services/scene_query.py`) — pure-ish function that composes the pgvector query (cosine distance on embedding) with the filters + shuffle strategy. No persistence beyond the snapshot export.

### Track search endpoint

#### `GET /admin/tracks/search?q=...`

Type-ahead search for the anchor picker. ILIKE on `title` joined to `artist.name`, limited to classified tracks (`classified_at IS NOT NULL`), capped at 20 results.

## Out of scope

- Saving / naming scenes for reuse (future sprint, after we know what configuration works)
- User-facing playlist generation endpoint (separate sprint built on POC findings)
- ML-trained ranking model — too early, baseline cosine-similarity must be characterized first
- Auto-evolving scenes (drift over time) — also future, depends on baseline working
- Persistence of "good / bad" labels beyond per-session snapshots — could later become labeled training data, but not yet
- Mobile-friendly UI for the workbench (desktop-only is fine for internal use)

## Done when

- Scene workbench page is reachable from the admin nav, gated by `is_admin`
- Can search for an anchor track and select 1+ as the scene's center
- All knobs (mood shift, vocals max, genre filter, pool size, shuffle strategy, anchor mode) work end-to-end
- Results re-query and render within a few hundred ms on knob changes
- Each result has a working SoundCloud embed player (for tracks that have a `soundcloud_url`)
- Snapshots export to JSON for review
- At least one round of trials documented (probably in `docs/scenes-poc-findings.md`) giving preliminary answers to each open question
- Findings translate into recommended defaults for the eventual user-facing playlist endpoint
