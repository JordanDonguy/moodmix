# Player Architecture

## Overview

The player system has three layers:

1. **YouTubePlayer** (`components/player/YouTubePlayer.tsx`) - manages the YouTube IFrame API, a fixed-position overlay, and all playback logic
2. **MixCard** (`components/mixes/MixCard.tsx`) - provides a positioning target for the overlay
3. **PlayerBar** (`components/layout/PlayerBar.tsx`) - bottom bar with progress, transport controls, volume

## Why a fixed overlay?

YouTube iframes reload when their DOM node is moved (browser spec). In a React list with keys, grid reflows (search result changes, items added/removed) can reorder DOM nodes - even if the component instance is preserved. Embedding the iframe directly inside a MixCard would cause playback to restart every time the grid updates.

**Solution:** The iframe lives in a `position: fixed` div appended to `document.body`. It never moves in the DOM. A `requestAnimationFrame` loop reads the active MixCard's `getBoundingClientRect()` every frame and positions the overlay on top of it.

```
document.body
  ├── #root (React app)
  │     ├── MixGrid
  │     │     └── MixCard (active) ← has a positioning-target div
  │     ├── PlayerBar
  │     └── YouTubePlayer (renders null)
  │
  └── div.fixed-overlay  ← created by YouTubePlayer, holds the iframe
        └── iframe (YouTube)
```

## Lifecycle

### Player creation
- `YouTubePlayer` mounts → creates the overlay div on `document.body` → loads the YT IFrame API → creates a single `YT.Player` instance inside the overlay
- The player is created **once** and never destroyed until `YouTubePlayer` unmounts

### Positioning
- `MixCard` sets `playerContainer` in the store when it becomes active (pointing to its thumbnail-area div)
- `YouTubePlayer` runs a rAF loop that reads `playerContainer.getBoundingClientRect()` and mirrors it onto the overlay's `top/left/width/height`
- When the card scrolls off-screen, the overlay hides; when it scrolls back, it reappears

### Video loading
- `currentMix` change → `loadVideoById()` (no player destruction/recreation)
- Play/pause → `playVideo()` / `pauseVideo()` synced from store

### Time tracking
- A `setInterval` (500ms) polls `player.getCurrentTime()` / `getDuration()` and writes to the store
- This is intentionally polled from the YouTube player (not computed from `Date.now()` deltas) so that seeks made via YouTube's own controls sync back to the app's progress bar

## Background tab handling

Browsers throttle background tabs and block autoplay. When a mix ends in a background tab:
1. `onStateChange: ENDED` fires → `next()` updates the store and calls `loadVideoById`
2. The browser may block autoplay for the new video
3. A `visibilitychange` listener detects when the tab becomes active again
4. If the store says `isPlaying` but the YT player isn't playing, it calls `playVideo()`

## Grid stability during search transitions

When a mix is playing and the user changes filters, the currently playing mix may not appear in the new results. `MixGrid` delegates list composition to the [`useAnchoredMixList`](../frontend/src/hooks/useAnchoredMixList.ts) hook, which uses a rotation strategy to minimize visible card movement:

### Cases

1. **`currentMix` not in results** → prepend it: `[currentMix, ...fetched]`. The playing card stays visible at position 0 so the user can still see/control it.
2. **`currentMix` in results, no previous prepend** → use fetched results as-is. This is the cold-start / normal-search case.
3. **`currentMix` in results, was prepended last render** → transition case. Instead of dropping the prepended mix from position 0 (which would shift every visible card up by one), the last fetched mix is "anchored" at position 0. Positions 1..N stay stable. The anchor mix moves from the bottom of the loaded list to the top — imperceptible in infinite-scroll contexts.

### Implementation

The hook maintains two refs across renders:
- `wasPrependingRef` — was the previous render prepending `currentMix`?
- `anchorRef` — the mix pinned at position 0 (if any)

The anchor is set on the prepending → not-prepending transition and persists until a new prepend starts (which invalidates it) or until the user plays the anchor itself (which drops it, accepting a one-time shift rather than pinning the playing mix at the top).

### Why not just pin the playing mix at position 0?

Early iteration. Rejected UX: clicking a mix deep in the list makes it "jump to the top," which is jarring when the user is browsing results. The rotation strategy keeps the playing mix in roughly its original position while still avoiding grid-wide shifts on transitions.

## Store shape (playerStore)

| Field | Type | Purpose |
|---|---|---|
| `currentMix` | `Mix \| null` | The mix being played |
| `queue` / `queueIndex` | `Mix[]` / `number` | Playback queue from the grid at time of click |
| `isPlaying` | `boolean` | Play/pause state |
| `currentTime` / `duration` | `number` | Progress (written by YouTubePlayer's polling interval) |
| `pendingSeek` | `number \| null` | Set by progress bar drag → consumed by YouTubePlayer |
| `volume` / `muted` | `number` / `boolean` | Volume state synced to YT player via store subscription |
| `playerContainer` | `HTMLDivElement \| null` | The active MixCard's thumbnail div (positioning target) |
