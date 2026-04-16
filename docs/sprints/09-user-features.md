# Sprint 9 — User Features

**Goal:** Liked mixes, cross-device preference sync, and time-of-day auto-mood for authenticated users.

**Depends on:** Sprint 8

## Scope

### Liked mixes & preference sync

#### Backend
- `user_likes` table (`user_id`, `mix_id`, `created_at`, PK on the pair)
- `user_preferences` table or columns on `users` (mood, energy, instrumentation defaults, instrumental flag, preferred genres, `auto_mood` flag)
- Endpoints: `POST /mixes/{id}/like`, `DELETE /mixes/{id}/like`, `GET /me/likes`, `GET /me/preferences`, `PUT /me/preferences`

#### Frontend
- Heart/like button on `MixCard` (optimistic update, syncs in background)
- On login: server preferences override `localStorage` (one-shot migration on first authenticated load)
- Anonymous users continue using `localStorage` — no behavior regression

### Account UI

- The current theme toggle button in the navbar is **replaced** by a user avatar button (no extra navbar real estate consumed)
- Logged out → avatar shows a generic icon, click opens auth modal (Sprint 8)
- Logged in → avatar shows initials/photo, click opens a dropdown menu
- Dropdown contents (top to bottom):
  - **My Library** → navigates to `/library`
  - Toggles: Auto-mood, Smart play
  - Theme toggle (moved here from the navbar)
  - **Legal & contact** → navigates to `/info` (Sprint 7 pages with sidebar nav)
  - **Sign out**
- No dedicated settings page in this sprint. Account-management actions (deletion, etc.) are handled via the contact form from Sprint 7. Email can't be changed (passwordless + OAuth makes it messy — users can create another account if needed). No password to change. Reconsider only if real demand surfaces.
- Mobile: same dropdown pattern as desktop, adapted for thumb ergonomics — ~90% viewport width, flush to the right edge, ~48px tap targets, 16px text minimum. Sticking with the dropdown (not a bottom sheet) because the fixed player bar already occupies the bottom of the screen and a sheet would either stack awkwardly above it or hide it. Better mobile UX (bottom-anchored navigation with sliding panels) is planned for Sprint 12 when the app is wrapped natively.

### Library page (`/library`)

- Dedicated route showing the user's liked mixes via the existing `MixGrid` component
- AI search bar hidden on this route
- Mood/energy/instrumentation sliders **stay visible and active**, but they **sort** the library by closeness to the slider values, not filter it (Euclidean distance on the mood vector). All saved mixes always remain visible.
- Genre dropdown still applies as a normal filter (since binary-match filtering on a small set is fine)
- Hint chip at the top: *"Sorted by closeness to your current mood. [Reset sliders]"* — makes the sort relationship explicit
- Slider state is shared with `/`, so "morning chill" preferences carry over: user lands on `/library` and instantly sees their most "morning chill"-like saved mixes first
- Search results from `/` are kept in React Query's cache (`staleTime` + `placeholderData: keepPreviousData`) so navigating back to `/` is instant with no skeleton flash

### Auto-mood (time of day)

- Toggle in preferences: "Auto-adjust mood by time of day"
- When enabled, **only the dark/bright slider** is time-derived on app load. The chill/dynamic and organic/electronic sliders are left at their normal defaults.
- Energy slider default (whether or not auto-mood is on): a slight tilt toward chill (~ -0.2). Background music is overwhelmingly chill-to-mid; very dynamic is the rare case. Open question — could also stay deactivated by default like currently. Decide during impl based on how it actually feels.
- Mapping for the dark/bright axis (rough starting point, refine during impl):
  - Early morning (6-9): bright (~ 0.5)
  - Morning (9-12): bright (~ 0.7)
  - Afternoon (13-17): slightly bright (~ 0.2)
  - Evening (17-21): slightly dark (~ -0.2)
  - Night (21-1): dark (~ -0.6)
  - Late night (1-6): very dark (~ -0.9)
- Implemented purely client-side using `Date` + the browser's local timezone — zero latency, no API call
- User can still override the slider manually after auto-set; auto-mood only seeds the initial value

#### Two possible behaviors (decide during impl)

1. **Seed only** — set the dark/bright slider on initial load, then leave it alone. Simple, predictable, no surprises.
2. **Continuous adjustment** — re-evaluate every ~30-60 min. If the time bucket has changed, update the slider and trigger a fresh search. Better for long sessions (e.g., user opens at 17:00, still listening at 22:00 — gets darker mixes automatically).

Continuous mode adds complexity: needs a timer, needs to detect when the user has manually overridden (and stop auto-adjusting after that for the session), needs to gracefully refetch without disrupting the currently-playing mix. Probably worth it, but keep "seed only" as a fallback if continuous turns out to be jarring in practice.

### Resume playback

Persist a single "where the user left off" pointer so that closing the app, switching devices, or doing the OAuth round-trip never loses listening context.

#### Storage

- **Authenticated** → `user_playback_state` table:
  ```sql
  CREATE TABLE user_playback_state (
      user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      mix_id UUID NOT NULL REFERENCES mixes(id) ON DELETE SET NULL,
      seconds_listened INTEGER NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```
- **Anonymous** → `localStorage.moodmix:playback` with the same shape (mix id + seconds + timestamp). Same read/write abstraction handles both backends.

#### Write triggers

- Throttled write every ~30s while a mix is playing
- Write immediately on mix change
- Final flush on `pagehide` via `navigator.sendBeacon` (auth) or `localStorage.setItem` (anonymous)
- TTL: **5 days** — older state isn't surfaced (user has moved on)

#### Read on app load → two-state player

Instead of surfacing resume as a grid card (easy to miss; depends on thumbnail aesthetics), the player bar itself is the resume affordance. Add a new player state:

- **State A — Hydrated** (new): player bar shows the mix's title, channel, thumbnail, and progress bar set to the saved seconds. Looks identical to a paused player. **No iframe loaded, no card prepended to the grid.**
- **State B — Active** (current behavior): iframe loaded in the overlay, card prepended/anchored in the grid, all existing playback logic runs.

User hits play in State A → transitions to State B by:
1. Setting `hydratedFromResume = false` in the player store
2. The existing iframe-creation effect kicks in (currently runs whenever `currentMix` is set; just gate it on `!hydratedFromResume`)
3. The iframe loads via `loadVideoById(mixId, savedSeconds)` — existing seek-on-load already supports this
4. Card is prepended via the existing `useAnchoredMixList` "currentMix not in fetched" branch

Implementation cost is small — `playerStore` gets one new flag (`hydratedFromResume`), `YouTubePlayer`'s iframe-creation effect gets one guard, transport controls already key off `currentMix` + `isPlaying` so they "just work."

#### OAuth round-trip handling

User starts playing anonymously, clicks "Sign in with Google," returns from OAuth callback. App reloads, now authenticated. Resume logic on app load:

1. Check DB resume state → empty (new account or stale)
2. Check `localStorage` resume state → found, surface in State A
3. Migrate the localStorage state into the DB so future device switches work
4. Same flow if the user signs in mid-listen (no special OAuth handling needed)

#### Backfill on login

When an anonymous user signs in mid-play with >30s on the current mix:
- Insert a `user_mix_plays` row with the captured `seconds_listened`
- Migrate the localStorage playback state to `user_playback_state`
- Continue tracking authenticated from there

#### Edge cases

- **Mix is unavailable on resume** → silently clear the resume state, render the empty player as if there were nothing to resume. Avoids repeated dead-resume on reopen.
- **Saved seconds > mix duration** (mix re-encoded etc.) → clamp to 0 and resume from start, don't error
- **Cross-device conflict**: last-write-wins by `updated_at`. User playing on phone, then laptop, then back to phone → phone reads DB on reopen, sees laptop's mix as most recent, surfaces that.

### Listening data collection

Separate from the resume pointer above — this is append-only history feeding analytics and future recommendations.

- `user_mix_plays` table: `id`, `user_id`, `mix_id`, `started_at`, `seconds_listened`, `completed`
- Indexes: `(user_id, started_at DESC)` and `(mix_id)`
- **Insert** when player crosses the **30s** threshold (filters out zappers without missing legitimate sampling)
- **Update** `seconds_listened` + `completed` on: mix change, mix end, page hide
- `completed = true` if `seconds_listened >= 80%` of `mix.duration_seconds`
- Use `navigator.sendBeacon` for the page-hide write (only API that survives unload)
- Anonymous users not tracked (no identity = no useful feature; aggregate analytics from authenticated plays is representative enough)
- **Backfill on auth**: if an anonymous user crosses the 30s threshold and then signs in, write the play row at sign-in time
- No UI in this sprint — pure data collection. Powers Sprint 10 product analytics, future recommendations, future history view if/when needed.

### Smart playing

- When the current mix ends, `next()` should pick the mix in the loaded list whose mood vector is closest to the currently playing one (Euclidean distance on `mood`, `energy`, `instrumentation`)
- Optionally bias toward genre overlap with the current mix
- Bias the dark/bright dimension toward the time-of-day target (so a 5h listening session naturally drifts brighter→darker as evening turns to night, even without auto-mood enabled)
- Skip mixes already played in the current session (track played-mix IDs in the player store)
- Pure client-side — works on whatever mixes are already loaded in `allMixes`. No backend changes needed.
- Falls back to sequential next-in-queue when fewer than ~5 unplayed mixes remain (so we don't keep playing the same neighbor cluster forever)
- Toggle in preferences: "Smart play" vs "Sequential queue". Default: smart play on.

### Weather based auto-mood (deferred / not committed)

- Punted from this sprint because it can't be a default-on-load value (weather API latency would block first paint or cause a visible mood "jump")
- Possible future approach: cache weather in `localStorage` on each visit; use the cached value as the next visit's default; refresh in the background. Adds complexity that's only worth it if user feedback asks for it.

## Out of scope

- Weather-based auto-mood (see above)
- Geolocation-based features
- Per-genre or per-mood notification preferences

## Decisions to make during impl

- Conflict resolution if a logged-in user has localStorage preferences from a prior session → server wins
- Auto-mood: seed-only vs continuous adjustment (see subsection above)
- Whether to make the time→mood mapping configurable (probably no — keep it opinionated)
- Smart play distance metric: pure mood-vector L2 distance, or weighted (e.g., energy and instrumentation matter more than mood for "feels similar")?
- Smart play + auto-mood interaction: should smart play *always* drift toward time-of-day, or only when auto-mood is enabled?
- Library: should genre dropdown filter, or also sort by best-match like the sliders? (probably filter — genre is binary)
- Avatar dropdown UX on tap-vs-click: ensure mobile dropdown doesn't dismiss prematurely on iOS Safari (known footgun)

## Done when

- Liking a mix persists across sessions and devices
- Logged-in users see preferences sync between devices
- Logged-out users see no behavior change
- Liked mixes appear at `/library`, navigable from the avatar dropdown
- Library page sorts (not filters) by current slider values; sliders carry over from `/` and back
- Avatar button replaces the navbar theme toggle; theme toggle moves into the dropdown
- Returning from `/library` to `/` shows the previous search results instantly (cached, no skeleton flash)
- Resume playback: closing the app or doing the OAuth round-trip surfaces the last-played mix in the player bar (State A — hydrated, no iframe loaded). Hitting play resumes from the saved position and prepends the mix card to the grid.
- Anonymous users get the same resume behavior via `localStorage`; on sign-in, that state migrates to the DB
- `user_mix_plays` rows are created for plays >30s, with `seconds_listened` and `completed` updated on mix change / end / page hide
- Auto-mood toggle, when enabled, sets a sensible dark/bright default based on local time without any perceptible delay on app load
- Energy slider default reflects the "background music is usually chill" insight (or stays neutral — decide during impl)
- Smart play: when enabled (default on), the next mix is the closest unplayed neighbor in the loaded list, with a time-of-day bias on the dark/bright dimension
- Smart play falls back to sequential next-in-queue when the loaded list is nearly exhausted
