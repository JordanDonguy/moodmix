# Sprint 12 — Admin Panel

**Goal:** Admin tooling to manage genre coverage, add artists, trigger Spotify/Deezer/Essentia/streaming-resolution work, and browse/preview tracks per artist with classification context.

**Depends on:** Sprint 11

## Scope

### Genre coverage dashboard

- Summary view: artist counts per resolution tier (confirmed / probable / ambiguous / failed), genre distribution across tracks
- Classification coverage: % of catalog with `classified_at IS NOT NULL`, % with at least one streaming URL, breakdown by has-SoundCloud / has-YouTube / has-both / has-neither
- Identify gaps: genres with low track counts, artists with 0 tracks despite having a `deezer_id`, artists with tracks but no classifications

### Artist management

- Browse and search artists by name, tier, genre, presence/absence of `deezer_id`
- Trigger Deezer top-track fetch for an artist
- Add a new artist manually (name + optional Spotify/Deezer ID) — kicks off classification + streaming-resolution Celery tasks scoped to that artist's tracks
- Trigger Spotify genres resolution for an artist
- Trigger Essentia classification for an artist (re-runs all unclassified tracks; or force-rerun by clearing `classified_at` first)
- Trigger streaming-link resolution for an artist
- Edit `resolution_tier` manually
- Edit genres (add/remove genre tags on an artist row)

### Track browser with audio preview

- Per-artist track list: title, duration, deezer_id, classification status (classified / pending), playback status (has SC / has YT / unplayable), mood vector chip ("Bright · Dynamic · Electronic")
- Inline Deezer embed player: clicking a track row loads the 30s preview for quick audition without leaving the panel
- Full-features view per track: pretty-printed `features` JSONB (BPM, key, all classifier probabilities, A/V regression, etc.) for validating classification quality during formula tuning
- Re-classify single track button (clears `classified_at`, kicks off classification task)
- Re-resolve streaming links single track button (clears `streaming_resolved_at`, kicks off resolution task)
- Delete unwanted tracks (CASCADE handles cleanup; replaces the old "exclude" flow)

### New-artist vetting flow

The primary use case is adding a new artist and confirming their tracks belong in the catalog before letting them surface in playlists:

1. Add artist via the "Add artist" form (name + optional Deezer ID)
2. Watch the track list populate as Deezer top-tracks fetch + import enrichment complete
3. Listen to a few previews via the inline player
4. If it fits MoodMix: trigger streaming resolution + classification (classification queued for the next local run — see Execution model below)
5. If it doesn't fit: delete the artist (CASCADE removes its tracks)

### Backend endpoints

- `GET /admin/artists` — paginated list with filters (tier, has_deezer_id, has_tracks, genre, classification_coverage)
- `GET /admin/artists/{id}/tracks` — track list for an artist (includes classification + streaming status)
- `POST /admin/artists` — create artist row
- `PATCH /admin/artists/{id}` — update tier, genres, deezer_id
- `POST /admin/artists/{id}/resolve-spotify` — trigger Spotify resolution
- `POST /admin/artists/{id}/fetch-deezer-tracks` — trigger Deezer top-50 fetch
- `POST /admin/artists/{id}/classify` — trigger Essentia classification for all unclassified tracks
- `POST /admin/artists/{id}/resolve-streaming` — trigger streaming-link resolution for all unresolved tracks
- `POST /admin/tracks/{id}/classify` — single-track re-classify
- `POST /admin/tracks/{id}/resolve-streaming` — single-track re-resolve
- `DELETE /admin/tracks/{id}` — remove a track

All routes gated by `is_admin` on the user row.

### Execution model

The VPS that hosts the API is small (2 vCPU / 4 GB / ARM64) — large enough for Deezer/Spotify API calls and yt-dlp searches, but **too small to run Essentia inference**. Classification therefore stays a local operation:

- **VPS-side** (runs on the API host directly, either inline for fast ops or in a small background process):
  - Deezer top-track fetch with metadata (loudness / isrc / release_date from Deezer)
  - Spotify metadata resolution (artist's genres)
  - Streaming-link resolution (yt-dlp)

- **Local-only** (Mac with the essentia-tensorflow Docker image):
  - Essentia classification

The admin's "Classify" trigger doesn't kick off remote work — it just **marks tracks for classification** (typically by clearing `classified_at` to NULL on a re-classify, or relying on the natural `IS NULL` filter for new tracks). A local script periodically pulls unclassified tracks from the remote DB, runs Essentia locally, and writes results back via the existing sync flow.

Once / if the API moves to a host with enough compute for Essentia, classification folds back into the same on-VPS execution path as the other triggers — the service interface is unchanged.

### sqladmin additions

- `ArtistAdmin`: image thumbnail, clickable Spotify/Deezer links in detail view, raw IDs in list
- `TrackAdmin`: inline audio player in detail view, duration formatted as M:SS, raw IDs in list, formatted `mood_vector`, pretty-printed `features` JSONB; `embedding` excluded from detail view (1280 floats unviewable)

The custom admin frontend above augments sqladmin for workflow-oriented tasks; sqladmin remains for raw DB access.

## Out of scope

- Public-facing artist or track pages
- Running Essentia inference on the VPS (current host can't support it; revisit on hardware upgrade)
- Background scheduler infrastructure for periodic resolution / enrichment (small inline workers are enough at current scale)
- Full RBAC beyond `is_admin` boolean
- Manual mood-formula tuning UI (handled via psql + re-deriving from `features` JSONB for now)

## Done when

- Classification + streaming coverage visible at a glance in the dashboard
- Can search, filter, and paginate artists by tier / genre / ID presence / classification coverage
- Can trigger Spotify resolution, Deezer track fetch, and streaming resolution from the UI per-artist and per-track (runs on VPS)
- "Classify" trigger marks tracks for local processing; local Essentia run picks them up and syncs results back
- Track list per artist shows classification status + mood chips + playback URLs alongside the 30s preview player
- All admin routes return 403 for non-admin users
