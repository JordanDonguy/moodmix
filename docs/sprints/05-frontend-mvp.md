# Sprint 5 — Frontend MVP

**Goal:** Functional React app where users can search mixes via sliders/genres/AI and play them with a persistent player bar.

**Depends on:** Sprint 3 (API endpoints working)

## Tasks

### 5.1 — Project scaffold
- [ ] Create `frontend/` with Vite + React + TypeScript template
- [ ] Install dependencies: `tailwindcss`, `framer-motion`, `zustand`, `@tanstack/react-query` (for data fetching)
- [ ] Configure Tailwind
- [ ] Set up API base URL via env var (`VITE_API_URL`)
- [ ] Create folder structure:
  ```
  frontend/src/
  ├── api/           -- API client functions
  ├── components/    -- UI components
  ├── hooks/         -- Custom hooks
  ├── store/         -- Zustand stores
  ├── types/         -- TypeScript types
  └── App.tsx
  ```

### 5.2 — TypeScript types + API client
- [ ] `types/mix.ts` — `Mix`, `Genre`, `SearchResponse`, `AiSearchResponse` types (mirror API response shapes)
- [ ] `api/client.ts` — base fetch wrapper with error handling
- [ ] `api/mixes.ts` — `searchMixes(params)`, `aiSearch(query)`, `reportUnavailable(id)`
- [ ] `api/genres.ts` — `getGenres()`

### 5.3 — Zustand store
- [ ] `store/searchStore.ts` — manages search/filter state:
  - `mood`, `energy`, `instrumentation` (slider values, default 0)
  - `selectedGenres: string[]` (genre slugs)
  - `instrumental: boolean` (default false)
  - Actions: `setValence()`, `setEnergy()`, `setInstrumentation()`, `toggleGenre()`, `toggleInstrumental()`
- [ ] `store/playerStore.ts` — manages playback state:
  - `currentMix: Mix | null` (the mix currently loaded in the player)
  - `isPlaying: boolean`
  - `progress: number` (0-100, from YouTube API events)
  - `duration: number` (total seconds)
  - `currentTime: number` (elapsed seconds)
  - Actions: `playMix(mix)`, `pause()`, `resume()`, `stop()`
- [ ] Persist slider + genre + instrumental state to `localStorage` on change
- [ ] Restore from `localStorage` on load

### 5.4 — Navbar (desktop): compact control bar
- [ ] `components/Navbar.tsx` — fixed top bar, ~80-100px height

**Desktop layout (~80px, single row):**
```
🌧️ ──────●────── ☀️ | 🛋️ ────●────── ⚡ | 🥁 ──●────── 💻 | (🎤) | Genres ▼ | [🔍 Search...]
```

- [ ] `components/MoodSlider.tsx` — compact slider component
  - Icons on left/right instead of text labels (saves space)
  - Hover on icon → tooltip shows the noun ("Sad" / "Happy")
  - Colored track gradient matching the mood dimension
  - Value range: -1 to 1, step 0.1
- [ ] 3 sliders side by side, separated by subtle dividers
- [ ] Debounced search trigger on slider change (~300ms)

- [ ] `components/VocalToggle.tsx` — 🎤 icon button
  - ON (instrumental only) = icon highlighted with accent color
  - OFF (all mixes) = icon dimmed/outline
  - Tooltip on hover: "Instrumental only" / "All mixes"

- [ ] `components/GenreDropdown.tsx` — dropdown panel
  - Button shows "Genres ▼" (or "Genres (3) ▼" when filters active)
  - Click opens dropdown panel with 14 genre chips in a grid
  - Chips are toggleable (filled = selected, outlined = not)
  - Multi-select
  - "Clear" button to deselect all
  - Close on click-outside
  - Selected count shown on the button

- [ ] `components/AiSearchBar.tsx` — search input
  - Compact text input with 🔍 icon
  - Expands on focus (framer-motion width transition)
  - On submit (Enter): call `POST /api/mixes/ai-search`
  - While loading: spinner replaces search icon
  - On response: animate sliders + genre chips to inferred values
  - Handle 429 (rate limit): show "Please wait" toast

### 5.5 — Navbar (mobile): collapsed
- [ ] `components/MobileNavbar.tsx`

**Mobile layout:**
```
🎵 MoodMix              [🎛️ Filters] [🔍]
```

- [ ] Tapping 🎛️ opens a **slide-down sheet** (framer-motion) with:
  - 3 sliders stacked vertically (full width, with text labels since there's room)
  - Genre chips in a scrollable grid
  - Vocal toggle
  - Sheet closes on swipe-down or tap-outside
- [ ] Tapping 🔍 opens AI search bar (full width, replaces navbar temporarily)
- [ ] Maximum screen real estate for the grid on mobile

### 5.6 — Results grid
- [ ] `components/MixGrid.tsx` — CSS grid container
  - Responsive: 1 col (mobile) / 2 cols (tablet) / 3 cols (desktop) / 4 cols (large)
  - Tailwind: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4`
  - Bottom padding to account for the player bar height

- [ ] `components/MixCard.tsx` — individual card
  - YouTube thumbnail image (full card width)
  - Title (truncated if long)
  - Channel name (smaller, muted text)
  - 3 mood indicator bars (`components/MoodBars.tsx`):
    - Valence: blue → orange gradient
    - Energy: blueish green → yellow gradient
    - Instrumentation: brown → purple gradient
    - Bar fill position based on -1 to 1 value
  - Genre tags as small badges
  - Subtle background tint derived from the mix's mood values (warm ↔ cool)
  - Click → calls `playerStore.playMix(mix)` → player bar starts playing
  - Currently playing card gets a visual indicator (accent border / "Now Playing" badge)

- [ ] Data fetched via react-query `useInfiniteQuery` keyed on search params

### 5.7 — Player bar (bottom, persistent)
- [ ] `components/PlayerBar.tsx` — fixed bottom bar, ~70-80px height

**Desktop layout:**
```
┌──────────────────────────────────────────────────────────────┐
│  [thumb]  Title - Channel     ◀◀  ▶/⏸  ▶▶    ───●───── 42:15 │
└──────────────────────────────────────────────────────────────┘
```

**Mobile layout:**
```
┌──────────────────────────────────────────────┐
│  [thumb]  Title - Channel       ▶/⏸          │
│  ─────────────●──────────────── 42:15        │
└──────────────────────────────────────────────┘
```

- [ ] Shows:
  - Small thumbnail (album art style)
  - Mix title + channel name (truncated)
  - Play/Pause button
  - Previous / Next buttons (desktop only — next/prev from current search results)
  - Progress bar (clickable to seek)
  - Elapsed time / total duration
- [ ] Hidden when no mix is playing (or show a subtle "Select a mix to play" placeholder)
- [ ] Framer-motion slide-up animation when first mix is played

### 5.8 — YouTube player (hidden)
- [ ] `components/YouTubePlayer.tsx` — hidden iframe, not visible to user
  - Wraps YouTube IFrame API
  - Load IFrame API script once on mount
  - Renders a hidden `<div>` that YouTube attaches its iframe to
  - Controlled entirely by `playerStore` (play, pause, seek)
  - Fires events back to `playerStore`: `onStateChange` (playing/paused/ended), `onProgress` (time updates), `onError`
- [ ] When `playerStore.currentMix` changes → load new video
- [ ] When video ends → auto-play next mix from current search results (if available)
- [ ] On error → report unavailable, auto-skip to next

### 5.9 — Dead video handling
- [ ] Listen for YouTube IFrame `onError` event
- [ ] On error:
  - Show toast notification: "This mix is no longer available, skipping..."
  - Gray out the card in the grid if still visible
  - Call `POST /api/mixes/{id}/report-unavailable` in background
  - Auto-skip to next mix in results

### 5.10 — Infinite scroll
- [ ] `hooks/useInfiniteScroll.ts` — IntersectionObserver on a sentinel element
- [ ] When sentinel is visible: fetch next page (offset += limit)
- [ ] Append to existing results
- [ ] Reset on any filter change (sliders, genres, instrumental, AI search)
- [ ] Show loading spinner at bottom while fetching

### 5.11 — localStorage persistence
- [ ] On load: restore last slider positions + selected genres + instrumental toggle from localStorage
- [ ] On change: save to localStorage (debounced)
- [ ] First visit (no localStorage): defaults (sliders at 0, no genres, instrumental off)

## Done when

- [ ] App loads at `localhost:5173` showing mixes grid with default [0,0,0] search
- [ ] Desktop navbar: 3 icon sliders + vocal toggle + genre dropdown + AI search — all in ~80px
- [ ] Mobile navbar: collapsed to logo + filter button + search icon
- [ ] Moving sliders updates results in real-time
- [ ] Genre dropdown filters results
- [ ] Vocal toggle works
- [ ] Clicking a card starts playback in the bottom player bar
- [ ] Player bar shows title, progress, play/pause/prev/next
- [ ] User can search for new mixes while current mix keeps playing
- [ ] AI search bar returns results and syncs sliders/chips
- [ ] Infinite scroll loads more results
- [ ] Refreshing the page restores last slider/genre state
- [ ] Dead videos are handled gracefully (toast + auto-skip)
