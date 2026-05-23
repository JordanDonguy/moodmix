# Sprint 10 — Artists & Tracks Catalog

**Goal:** Build the track catalog layer — artists and tracks models, Spotify/Deezer resolution pipeline, and all associated scripts for ingestion and recovery. This is to prepare for later track pivot so we can ultimatly build dynamic playlists with tracks properly classified instead of relying on static yt mixes for playback.

**Depends on:** Sprint 9

## Scope

### Data models

#### `artists` table

- `id` UUID PK
- `name` TEXT NOT NULL
- `spotify_id` TEXT UNIQUE
- `deezer_id` TEXT UNIQUE
- `image_url` TEXT
- `genres` TEXT[] (Spotify genres preferred; Deezer genres used as fallback when Spotify is empty)
- `resolution_tier` TEXT CHECK IN ('confirmed', 'probable', 'ambiguous', 'failed')
- `created_at`, `updated_at`
- Expression index: `LOWER(name)` UNIQUE for case-insensitive dedup

#### `tracks` table

- `id` UUID PK
- `artist_id` UUID FK → artists (CASCADE on delete)
- `title` TEXT NOT NULL (cleaned via `clean_track_title()`)
- `isrc` TEXT (nullable — used as universal join key across providers)
- `deezer_id` TEXT UNIQUE
- `duration_ms` INTEGER
- `release_date` DATE
- `created_at`, `updated_at`
- Partial index on `isrc` (WHERE NOT NULL)

Audio classification and streaming-resolution columns are added in Sprint 11. Several columns initially scoped here (`deezer_album_id`, `preview_url`, `status`, `exclusion_reason`, `raw_artists`, `raw_genres`) were dropped before Sprint 11 — see [Sprint 11](11-classification-and-embedding.md) for the rationale.

### Services

#### `SpotifyClient` (`app/services/spotify_client.py`)

- OAuth2 client-credentials with token caching (no refresh needed — 1h TTL)
- 429 + 5xx retry with exponential backoff
- Methods: `search_artist()`, `get_artist()`, `get_artist_albums()`, `get_album_tracks()`, `get_tracks()` (batch 50), `get_artist_top_tracks()`

#### `DeezerClient` (`app/services/deezer_client.py`)

- No auth required for public read endpoints
- 429 + Deezer quota error (code 4) backoff
- Methods: `search_artist()`, `get_artist_top_tracks()`, `get_track_by_isrc()` (None on code 800), `get_album()`

### Scripts

All scripts are idempotent. Run in order for initial ingestion:

#### 1. `resolve_artists.py`

Seeds artists from a JSON file, then resolves each against Spotify:
- `clean_name()` strips channel decoration (`| *Artist*` format, brackets, trailing ` - Topic`)
- `normalize_for_match()` strips to alphanumeric-only for fuzzy matching
- Searches Spotify (limit 50), scores candidates by name match
- Assigns resolution tier: confirmed / probable / ambiguous / failed

#### 2. `dump_genre_verdicts.py`

Classifies artists by genre using Spotify genre strings and `ALLOW_PATTERNS` / `DENY_PATTERNS`. Writes `data/genre_verdict.json` for review.

#### 3. `rescue_drop_artists.py`

Re-resolves drop artists (a genre subtype) with a broader Spotify search (limit 50). Filters by allow-genre after resolution.

#### 4. `merge_duplicate_artists.py`

Fetches Spotify canonical name via `spotify_id`, deletes ambiguous twins with the same normalized name, renames confirmed rows to canonical form.

#### 5. `backfill_chapter_tracks.py`

Inserts tracks from YouTube mix chapters into the `tracks` table:
- Three-level artist lookup: by lower name → by cleaned lower name → by alphanumeric-only normalized name
- Collab splitting via `primary_artist()` (handles "A & B", "A, B", "A ft. B")
- `clean_track_title()` applied at insert time (strips URLs, asterisks, label tags, Forthcoming tags, dash version labels)

#### 6. `resolve_deezer_artists_and_tracks.py`

Main Deezer resolver — for each confirmed/probable artist with no `deezer_id`:
- Searches Deezer by name (up to 10 candidates)
- Fetches top-50 tracks per candidate
- Cross-references against existing chapter tracks via `normalize_track_title()`
- On match: sets `deezer_id` on artist, upserts tracks (updates title + deezer_id on chapter-track hits, inserts new)
- No match: sets tier to `ambiguous`

#### 7. `find_deezer_artists_via_album_genres.py`

Recovery for ambiguous artists (Spotify-free path):
- Searches Deezer by name, name-match guard via `_name_matches()` (normalized substring overlap)
- Walks candidate's top-track albums, fetches genres for each
- Deny-wins verdict: any deny-pattern genre rejects the candidate
- On allow: writes match to `data/deezer_artist_candidates.json`
- On no match: writes breadcrumbs to `no_match` bucket for review
- `_fixup_existing_matches()` retroactively re-validates existing JSON entries against updated patterns
- Output is a review file — does NOT update the DB directly

#### 8. `apply_deezer_artist_candidates.py`

Applies `data/deezer_artist_candidates.json` to the DB:
- Sets `deezer_id` on artist (skips if already set or ID already claimed)
- Sets `genres` only if currently null/empty (Spotify genres take precedence)
- Leaves tier at `ambiguous` — tracks fetch happens next

#### 9. `fetch_tracks_for_recovered_artists.py`

Fetches top-50 Deezer tracks for tier ∈ (probable, ambiguous) + `deezer_id` NOT NULL:
- Upserts tracks via same `_ingest_tracks_for_artist()` logic as the main resolver
- Flips tier to `confirmed` after successful fetch

### Track title utilities (`scripts/_track_title.py`)

- `clean_track_title()` — strips URLs, asterisks, label tags (`[Monstercat]` etc.), `Forthcoming` prefixes, trailing version labels in dash format (` - Radio Edit`, ` - Extended Mix`, etc.)
- `normalize_track_title()` — further collapses feat. variants, track numbers, parenthetical version labels, for cross-provider fuzzy matching

## Out of scope

- User-facing track browsing or playback endpoints (later sprint)
- Audio analysis / classification / embeddings (Sprint 11)
- Streaming-platform URL resolution for playback (Sprint 11)

## Done when

- `artists` and `tracks` tables exist with migrations
- All resolution scripts run end-to-end without errors
- Confirmed artists have `deezer_id` set and tracks ingested
- Chapter-to-track backfill links tracks to their artist rows
- Track titles are cleaned of decoration noise
- ~75k tracks in DB across confirmed + recovered artists
