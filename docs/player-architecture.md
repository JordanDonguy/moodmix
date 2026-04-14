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
