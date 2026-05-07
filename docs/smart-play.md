# Smart Play

Auto-advances to the next mix based on mood and genre similarity instead of blindly following the loaded list. The goal is a "DJ handoff" feel — each transition sounds intentional.

## Overview

When smart play is enabled, `playerStore.next()` delegates to `computeNextMix` instead of incrementing a queue index. The algorithm picks the closest mix from the currently loaded pool using a three-tier genre + mood-vector strategy.

The feature is opt-out (on by default) and persisted per device. The toggle lives in the app menu and takes effect immediately for the current session.

## Algorithm

The core logic is a pure function — no React, no store — in [`frontend/src/lib/smartPlay/computeNextMix.ts`](../frontend/src/lib/smartPlay/computeNextMix.ts).

### Candidate filtering

Before ranking, three categories are excluded:

- The current mix itself
- Mixes the user has already heard this session (`playedMixIds`)
- Unclassified mixes (any of `mood`, `energy`, `instrumentation` is `null`)

### Three-tier selection

```
┌─────────────────────────────────────────────────┐
│ Tier 1 — Exact genre set match                  │
│  Same genres, same count                        │
│  If multiple: pick closest by mood-vector       │
└──────────────────────┬──────────────────────────┘
                       │ no exact match
                       ▼
┌─────────────────────────────────────────────────┐
│ Tier 2 — Partial genre overlap                  │
│  At least one shared genre                      │
│  Ranked by overlap count; mood-vector breaks    │
│  ties within the highest-overlap bucket         │
└──────────────────────┬──────────────────────────┘
                       │ no overlap (or current has no genres)
                       ▼
┌─────────────────────────────────────────────────┐
│ Tier 3 — Mood-only fallback                     │
│  No genre filter — pick the mood-vector         │
│  closest from everything available              │
└─────────────────────────────────────────────────┘
```

Genre overlap takes priority over mood distance. A mix from the same genre that's 20% moodier will beat a mood-perfect match from a completely different genre. This matches how a human DJ thinks: genre is the room, mood is the energy level within it.

### Mood-vector distance

Euclidean (L2) distance across the three classification axes — the same metric the backend uses for slider-driven search:

```
d = √( (mood_a − mood_b)² + (energy_a − energy_b)² + (instrumentation_a − instrumentation_b)² )
```

All three axes are on the same 0–100 scale, so the distance is unweighted. Unclassified mixes are excluded before reaching `pickClosest`, so null-coalescing to 0 inside the formula is purely defensive.

## Pool management

Smart play needs a live candidate pool. The pool is maintained by `MixGrid` and written into the player store:

```
┌───────────────────────────────────────────────────┐
│ MixGrid — infinite scroll                         │
│  useInfiniteQuery → fetchedMixes (memo)           │
│                                                   │
│  useEffect → playerStore.setAvailableMixes(...)   │
│  (fires whenever a new page loads)                │
└───────────────────────┬───────────────────────────┘
                        │ availableMixes[]
                        ▼
┌───────────────────────────────────────────────────┐
│ playerStore.next()                                │
│  computeNextMix(currentMix, availableMixes,       │
│                 playedMixIds)                     │
└───────────────────────────────────────────────────┘
```

`availableMixes` is whatever the grid has fetched so far — it grows as the user scrolls and shrinks to the new result set whenever search params change.

### Played-mix tracking

`playedMixIds` is a `Set<string>` in the player store. It accumulates the IDs of every mix the user has auto-advanced past in the current session. Excluded from `computeNextMix` candidates so the algorithm never short-loops between two similar mixes.

A manual `playMix` call (the user clicks a card) clears the set — a user-driven play resets the implicit "auto-flow" starting from the new pick.

### Proactive prefetch

To prevent pool exhaustion before infinite scroll naturally fires, `MixGrid` watches the unplayed pool size:

```ts
const unplayed = fetchedMixes.length - playedMixIds.size;
if (unplayed < 5 && hasNextPage && !isFetchingNextPage) {
    fetchNextPage();
}
```

This keeps fresh candidates loading in the background. In practice the threshold of 5 means a new page is in flight well before `computeNextMix` would hit the exhaustion fallback.

### Pool exhaustion fallback

If `computeNextMix` returns `null` (all loaded mixes have been played), `next()` resets `playedMixIds` to just the current mix and tries once more. Repetition is preferable to silence — and the proactive prefetch makes this fallback rarely fire in practice.

## Sequential mode (smart play off)

When `settingsStore.smartPlay` is `false`, `next()` skips `computeNextMix` entirely and advances the queue index:

```
currentMix = queue[queueIndex + 1]
```

`queue` is the `allMixes` array from the grid at the time the user pressed play on a card. This is the predictable "next in line" behaviour users expect from a standard playlist.

## Settings persistence

`settingsStore` is a Zustand store with the `persist` middleware, writing to `localStorage["moodmix-settings"]`. The toggle survives page reloads on a given device. Cross-device preference sync is out of scope until the user profile feature ships.

## File map

| File | Role |
|---|---|
| [`frontend/src/lib/smartPlay/computeNextMix.ts`](../frontend/src/lib/smartPlay/computeNextMix.ts) | Pure algorithm — genre tiers + mood-vector distance |
| [`frontend/src/store/settingsStore.ts`](../frontend/src/store/settingsStore.ts) | `smartPlay` boolean, persisted |
| [`frontend/src/store/playerStore.ts`](../frontend/src/store/playerStore.ts) | `availableMixes`, `playedMixIds`, `setAvailableMixes`; `next()` branches on `smartPlay` |
| [`frontend/src/components/mixes/MixGrid.tsx`](../frontend/src/components/mixes/MixGrid.tsx) | Syncs loaded mixes to store; proactive prefetch effect |
| [`frontend/src/components/ui/ToggleSwitch.tsx`](../frontend/src/components/ui/ToggleSwitch.tsx) | Reusable iOS-style pill toggle |
| [`frontend/src/components/ui/Tooltip.tsx`](../frontend/src/components/ui/Tooltip.tsx) | CSS-only tooltip (instant hover, no OS delay) |
| [`frontend/src/components/layout/AppMenu.tsx`](../frontend/src/components/layout/AppMenu.tsx) | Smart play row in the app menu |
