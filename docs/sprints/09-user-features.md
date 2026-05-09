# Sprint 9 — User Features

**Goal:** Mix playback persistence across sessions and devices, login-time state migration, and smart auto-play.

**Depends on:** Sprint 8

## Scope

### Playback persistence

Persist a single "where the user left off" pointer so closing the app, switching devices, or doing the OAuth round-trip never loses listening context.

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
- TTL: **5 days** — older state is not surfaced

#### Read on app load → two-state player

- **State A — Hydrated**: player bar shows the mix's title, channel, thumbnail, and progress bar set to the saved seconds. No iframe loaded, no card prepended to the grid.
- **State B — Active**: iframe loaded in the overlay, card prepended/anchored in the grid, all playback logic runs.

User hits play in State A → transitions to State B:
1. Clears `hydratedFromResume` flag in the player store
2. The existing iframe-creation effect kicks in (gated on `!hydratedFromResume`)
3. The iframe loads via `loadVideoById(mixId, savedSeconds)`
4. Card is prepended via the existing `useAnchoredMixList` branch

#### Edge cases

- **Mix unavailable on resume** → silently clear resume state, render empty player
- **Saved seconds > mix duration** → clamp to 0
- **Cross-device conflict** → last-write-wins by `updated_at`

### Persistence on login

When an anonymous user signs in:
1. Check DB resume state → if empty, check `localStorage` resume state
2. If found in `localStorage`, surface in State A
3. Migrate localStorage state into the DB so future device switches work
4. If the user was mid-play with >30s: insert a `user_mix_plays` row with captured `seconds_listened`, then continue tracking authenticated

### Smart play

- When the current mix ends, `next()` picks the mix in the loaded list whose mood vector is closest to the currently playing one (Euclidean distance on `mood`, `energy`, `instrumentation`)
- Optionally bias toward genre overlap with the current mix
- Skip mixes already played in the current session (track played-mix IDs in the player store)
- Falls back to sequential next-in-queue when fewer than ~5 unplayed mixes remain
- Toggle in preferences: "Smart play" vs "Sequential queue". Default: smart play on.
- Pure client-side — works on whatever mixes are already loaded in `allMixes`. No backend changes needed.

## Done when

- Closing the app or doing the OAuth round-trip surfaces the last-played mix in the player bar (State A — hydrated, no iframe loaded)
- Hitting play resumes from the saved position and prepends the mix card to the grid
- Anonymous users get the same resume behavior via `localStorage`; on sign-in, that state migrates to the DB
- Smart play: when enabled (default on), the next mix is the closest unplayed neighbor in the loaded list
- Smart play falls back to sequential next-in-queue when the loaded list is nearly exhausted
