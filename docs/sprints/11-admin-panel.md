# Sprint 11 — Admin Panel

**Goal:** Admin tooling to manage genre coverage, add artists, trigger Spotify/Deezer fetches, and browse/preview tracks per artist.

**Depends on:** Sprint 10

## Scope

### Genre coverage dashboard

- Summary view: artist counts per resolution tier (confirmed / probable / ambiguous / failed), genre distribution across tracks
- Identify gaps: genres with low track counts, artists with 0 tracks despite having a `deezer_id`
- Surface ambiguous artists still needing manual review

### Artist management

- Browse and search artists by name, tier, genre, presence/absence of `spotify_id` / `deezer_id`
- Add a new artist manually (name + optional Spotify/Deezer ID)
- Trigger Spotify resolution for an artist → runs `resolve_artists` logic inline, updates tier and IDs
- Trigger Deezer top-track fetch for an artist → runs `_ingest_tracks_for_artist` inline, inserts/updates tracks
- Edit `resolution_tier` manually (e.g. force-confirm after eyeballing the JSON, or mark as failed)
- Edit genres (add/remove genre tags on an artist row)

### Track browser with audio preview

- Per-artist track list: title, duration, deezer_id, preview_url, status (active / excluded)
- Inline Deezer embed player: clicking a track row loads the 30s preview so the track can be quickly auditioned without leaving the admin panel
- Toggle track status (active ↔ excluded) with an optional exclusion reason
- Bulk exclude tracks by title pattern or keyword match

### Artist vetting flow

The primary use case is reviewing recovered ambiguous artists before committing them:

1. Open artist → see resolution tier, genres, track list
2. Listen to a few track previews via the inline player
3. If it fits MoodMix: confirm tier manually or trigger a full Deezer fetch
4. If it doesn't fit: mark as failed, optionally bulk-exclude its tracks

### Backend endpoints

- `GET /admin/artists` — paginated list with filters (tier, has_deezer_id, has_tracks, genre)
- `GET /admin/artists/{id}/tracks` — track list for an artist
- `POST /admin/artists` — create artist row
- `PATCH /admin/artists/{id}` — update tier, genres, deezer_id, spotify_id
- `POST /admin/artists/{id}/resolve-spotify` — trigger Spotify resolution
- `POST /admin/artists/{id}/fetch-deezer-tracks` — trigger Deezer top-50 fetch
- `PATCH /admin/tracks/{id}` — update status, exclusion_reason
- `POST /admin/tracks/bulk-exclude` — exclude by pattern

All routes gated by `is_admin` on the user row.

### sqladmin additions (already done in Sprint 10)

- `ArtistAdmin`: image thumbnail, clickable Spotify/Deezer links in detail view, raw IDs in list
- `TrackAdmin`: inline audio player in detail view, duration formatted as M:SS, raw IDs in list

The custom admin frontend above augments sqladmin for workflow-oriented tasks; sqladmin remains for raw DB access.

## Out of scope

- Public-facing artist or track pages
- Automated nightly resolution jobs (those are script runs for now)
- Full RBAC beyond `is_admin` boolean

## Done when

- Genre coverage summary visible with per-tier artist counts and track distribution
- Can search, filter, and paginate artists by tier/genre/ID presence
- Can trigger Spotify resolution and Deezer track fetch from the UI for a single artist
- Track list per artist shows with playable 30s Deezer previews
- Can toggle track active/excluded status individually or in bulk
- Artist tier and genres editable from the UI
- All admin routes return 403 for non-admin users
