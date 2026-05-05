# Resume Playback

Lets a user pick up where they left off after closing the tab, switching devices, or doing the OAuth round-trip — without losing the listening context.

## Overview

The system tracks **one** "where you left off" pointer per identity (one row per authed user, one localStorage entry per anon device). On reopen, the pointer hydrates the player into a paused, idle state showing the saved mix and timestamp. Hitting play loads the iframe at the saved seconds and resumes normally.

Two storage backends share an interface so the rest of the code never branches on auth state:

| Identity | Backend | Lifecycle |
|---|---|---|
| Authenticated | `user_playback_state` table | Cross-device, last-write-wins by `updated_at` |
| Anonymous | `localStorage["moodmix:playback"]` | Single-device. Migrates to server on sign-in. |

A 5-day TTL filter (read-time) drops stale offers — a user who hasn't been around in a week shouldn't see a "resume" prompt for a mix they've forgotten about.

## Two-state player model

The new bit on top of the existing player is a "hydrated but inert" mode:

```
┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐
│ State A — Hydrated                   │    │ State B — Active                     │
│  • PlayerBar shows mix metadata      │    │  • iframe loaded with the mix        │
│  • Progress bar at saved seconds     │    │  • Card prepended/anchored in grid   │
│  • iframe NOT loaded (lightweight)   │    │  • Tracking interval running         │
│  • Card NOT prepended in grid        │    │  • All existing playback logic       │
│                                      │    │                                      │
│  hydratedFromResume = true           │    │  hydratedFromResume = false          │
│  isPlaying = false                   │    │  isPlaying = (true on play press)    │
└──────────────────────────────────────┘    └──────────────────────────────────────┘
                  │                                          ▲
                  └──────── press play / next / prev ────────┘
                              (any explicit play action)
```

`hydratedFromResume` is the single store flag that distinguishes the two. It flips false in the player store's `playMix`, `next`, `prev`, and `resume` actions — anything that represents an explicit play action. The flag gates two things:

- **In `YouTubePlayer`**, the `loadVideoById` calls (both the initial one in `onReady` and the load-on-mix-change effect)
- **In `useAnchoredMixList`**, the `shouldPrepend` decision

Everything else (PlayerBar, NowPlayingInfo, ProgressBar) renders normally — they just see the `currentMix` and `currentTime` from the store and don't care about the flag.

## Storage

### Schema

```
user_playback_state
─────────────────────
user_id            UUID  PK    FK→users (ON DELETE CASCADE)
mix_id             UUID        FK→mixes (ON DELETE SET NULL)
seconds_listened   INT
updated_at         TIMESTAMPTZ
```

`ON DELETE SET NULL` on `mix_id` matters: if a mix gets removed, we don't cascade-delete the user's row. The read path treats `mix_id IS NULL` as "nothing to resume" — same outcome the user would have seen anyway, no error noise.

`localStorage` mirrors the shape:

```ts
{ mix_id: string, seconds_listened: number, updated_at: string }
```

Stored as JSON under the key `"moodmix:playback"`. Same TTL policy applied at read time.

### TTL

5 days, applied at read time in [`PlaybackStateService.get`](../backend/app/services/playback_state_service.py) (server) and [`localPlaybackRepo.get`](../frontend/src/lib/playback/localPlaybackRepo.ts) (anon). Both return `null` for expired rows. No background cleanup yet — that lands with Sprint 11's job runner.

## Write triggers

```
            ┌───────────────────────────────────────────────────────┐
            │  player store  (currentMix, currentTime, isPlaying)   │
            └───────────────────────┬───────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────────────┐
            ▼                       ▼                               ▼
  ┌──────────────────┐    ┌──────────────────┐         ┌────────────────────┐
  │ Throttled poll   │    │ Mix-change sub.  │         │ pagehide listener  │
  │ every 5s, gated  │    │ subscribe(prev,  │         │ window.addEventL.  │
  │ by 30s throttle  │    │  next) on store  │         │                    │
  │                  │    │                  │         │  authed → fetch    │
  │ writes via repo  │    │ writes via repo  │         │   ({keepalive})    │
  │                  │    │                  │         │  anon  → localStg  │
  └────────┬─────────┘    └────────┬─────────┘         └─────────┬──────────┘
           │                       │                             │
           └───────────────────────┴─────────────────────────────┘
                                   │
                                   ▼
                       ┌─────────────────────┐
                       │ PlaybackRepo (auth) │
                       │ usePlaybackRepo()   │
                       │  → server | local   │
                       └─────────────────────┘
```

All three live in [`hooks/playback/usePersistPlaybackProgress.ts`](../frontend/src/hooks/playback/usePersistPlaybackProgress.ts).

### Throttle (~30s)

A 5s `setInterval` polls. If 30s have elapsed since the last write AND the player is actively playing AND we're not in State A, write the current `(mix_id, currentTime)`. The polling-then-gate pattern (vs. a strict 30s interval) lets us reuse the same loop for future event-driven writes if needed and adapts gracefully if writes get re-issued by the immediate handler.

### Immediate on mix change

Subscribed to `playerStore.subscribe`. On every state change, check whether `currentMix.id` differs from the previous tick. If yes, write the new mix at its current time (typically 0 — playMix/next/prev all reset `currentTime`). The resume pointer follows "what the user is listening to *now*," even if the throttle window hasn't elapsed.

This also resets the throttle's `lastWriteRef`, so the next throttled write happens 30s after the change.

### Pagehide (final flush)

Authed users use `fetch({ keepalive: true })` — the modern equivalent of `sendBeacon` that **also** honors CORS preflight. (`sendBeacon` silently drops `application/json` cross-origin because it can't preflight; we tried it first and lost writes.) Anonymous users do a synchronous `localStorage.setItem` which always succeeds.

Failure here only loses up to ~30s of progress because the throttled writer has already saved a recent value during the session.

### Why skip writes in State A

If we wrote with `hydratedFromResume = true`, every page load would re-stamp the row with the *same* `(mix_id, seconds)` it just *read* — only `updated_at` would change. Two real problems:

1. **TTL semantics break.** A user who lands on the page once after 6 days would have their resume row's `updated_at` ticked forward, resurrecting a stale offer indefinitely.
2. **Cross-device last-write-wins gets corrupted.** Phone (last played 5:30) opens after Laptop (last played 12:45). If Phone re-stamps its old row, Phone's stale 5:30 now looks "newer" than Laptop's 12:45.

The writer skips entirely until the user presses play and the flag flips false.

## Read on mount (with sign-in migration folded in)

[`hooks/playback/useResumePlaybackOnMount.ts`](../frontend/src/hooks/playback/useResumePlaybackOnMount.ts) runs once after auth has hydrated. For authed users it does a migration step before the read, so a localStorage pointer left over from a prior anon session — most commonly the one that survived the OAuth round-trip — gets promoted to the server first.

```
┌──────────────────────────────────────────────────┐
│ Wait for `useAuthStore.hydrated === true`        │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ If authed AND localStorage has state:            │
│   PUT to server → clear localStorage             │
│ (best-effort; failures retry on next reload)     │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ Pick repo via usePlaybackRepo()                  │
│ (server if authed, local if anon)                │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ repo.get()                                       │
│  • null (no state, expired, or mix_id=null) → ∅  │
│  • PlaybackState → continue                      │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ getMix(state.mix_id)                             │
│  • 200 → continue                                │
│  • 404/410 → repo.clear() + return               │
│  • network error → return (retry next reload)    │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ playerStore.hydrateFromResume(mix, seconds)      │
│  → State A active                                │
└──────────────────────────────────────────────────┘
```

A `ranRef` ensures the effect fires once per mount; sign-in/sign-out within the same session don't trigger a re-resume.

### Why migration lives here, not in a separate "on sign-in" hook

The OAuth flow is `window.location.href = ${API}/auth/google`, which is a real navigation. After Google's callback, the backend redirects back to the frontend and the page **reloads**. So from the SPA's perspective, "the user just signed in" looks identical to "a returning authed user opened the app." A separate hook listening for `null → User` transitions never sees the change because by the time it mounts, the auth store hydrates straight to `User`.

Folding migration into `useResumePlaybackOnMount` solves this — on every mount where the user is authed, we check localStorage, push it to the server if present, and then read.

### Email-code sign-in: clear localStorage immediately

The email-code modal is the one path that signs the user in **without** a reload. There, localStorage gets *frozen* at its last anon-era value (subsequent writes go to the server now). If the user listens long enough that the server's state surpasses localStorage and *then* reloads, the migration step would overwrite the fresher server state with the stale local copy.

To prevent that, [`useSigninFlow.verifyAndSignIn`](../frontend/src/hooks/useSigninFlow.ts) calls `localPlaybackRepo.clear()` right after `setUser`. From that moment on, localStorage is empty, future writes flow to the server, and a later reload's migration step finds nothing to migrate. The pagehide handler still flushes to the server (the user is authed by then), so no progress is lost in the window between sign-in and the next throttled write.

The OAuth path doesn't go through `verifyAndSignIn`, so localStorage *survives* that flow — and that's exactly what we want, because the post-callback reload's migration is the one place where localStorage *is* the freshest source.

## Edge cases

| Case | Behavior |
|---|---|
| Saved mix has been removed (`unavailable_at`, deletion) | `getMix` 404s → `repo.clear()` → render empty player |
| Saved seconds > mix duration (mix re-encoded) | `loadVideoById(mix, seconds)` clamps internally; player resumes from start |
| Cross-device conflict (Phone vs Laptop) | Last-write-wins by `updated_at`; the device that opens later sees the most recent state |
| User never presses play after hydrate | No writes happen (State A skip); pointer stays as-is until TTL expires |
| OAuth round-trip mid-listen | Anon writes accumulate to localStorage during sign-in flow; migration hook moves them to server after the redirect resolves |
| `fetch({ keepalive: true })` rejected | Best-effort; throttled writes already persisted recent values, so worst case is ~30s of lost progress |

## File map

The resume-playback machinery is split across a few directories. Reading them in this order is a sensible on-ramp:

| File | Role |
|---|---|
| [`backend/app/models/user_playback_state.py`](../backend/app/models/user_playback_state.py) | ORM model — one row per user |
| [`backend/app/services/playback_state_service.py`](../backend/app/services/playback_state_service.py) | `get` (with TTL filter), `upsert` (Postgres `ON CONFLICT`), `clear` |
| [`backend/app/routers/playback.py`](../backend/app/routers/playback.py) | `GET / PUT / DELETE /api/playback/state`, all auth-gated |
| [`frontend/src/api/playback.ts`](../frontend/src/api/playback.ts) | Typed wrappers + the `PLAYBACK_STATE_URL` constant for `keepalive` fetch |
| [`frontend/src/lib/playback/localPlaybackRepo.ts`](../frontend/src/lib/playback/localPlaybackRepo.ts) | localStorage backend, same shape, same TTL |
| [`frontend/src/lib/playback/repo.ts`](../frontend/src/lib/playback/repo.ts) | `PlaybackRepo` interface + server/anon adapters |
| [`frontend/src/hooks/playback/usePlaybackRepo.ts`](../frontend/src/hooks/playback/usePlaybackRepo.ts) | Auth-aware resolver — picks the right backend |
| [`frontend/src/hooks/playback/useResumePlaybackOnMount.ts`](../frontend/src/hooks/playback/useResumePlaybackOnMount.ts) | Hydrate-on-mount flow + localStorage→server migration for authed users |
| [`frontend/src/hooks/playback/usePersistPlaybackProgress.ts`](../frontend/src/hooks/playback/usePersistPlaybackProgress.ts) | The three write triggers |

## Player store additions

| Field | Type | Purpose |
|---|---|---|
| `hydratedFromResume` | `boolean` | True only in State A — gates iframe load + grid prepend |
| `hydrateFromResume(mix, seconds)` | action | Sets `currentMix`, seeds `currentTime`, flag = true |

The existing `playMix`, `next`, `prev`, and `resume` actions all clear `hydratedFromResume` as a side effect — any explicit play action transitions out of State A.
