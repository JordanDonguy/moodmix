# Sprint 11 — Classification & Embedding

**Goal:** Deterministic audio classification of every track in the catalog (mood, energy, instrumentation derived from Essentia features), 1280-d embeddings for similarity search, and playback-URL resolution against SoundCloud + YouTube. Ship reusable per-track and per-artist services so the same pipeline runs on new additions without re-engineering.

**Depends on:** Sprint 10

## Scope

### Schema changes

Migrations `011` → `013` modify the `tracks` table.

**Added** (all nullable; populated by backfill jobs over time):

- `mood_vector` `vector(3)` — derived 3D vector (mood, energy, instrumentation)
- `embedding` `vector(1280)` — Effnet-Discogs mean-pooled track embedding for cosine similarity
- `classification_confidence` REAL
- `loudness_db` REAL — Deezer's ReplayGain (more accurate than Essentia's 30s-window value)
- `features` JSONB — every raw Essentia output (BPM, key, all classifier probabilities, A/V regression, spectral centroid)
- `classifier_version` TEXT
- `classified_at` TIMESTAMPTZ — `IS NOT NULL` is the canonical "ready" check
- `soundcloud_url` TEXT — primary playback source
- `youtube_video_id` TEXT — fallback playback source
- `streaming_resolved_at` TIMESTAMPTZ — mirror of `classified_at` for the streaming-resolution job

**Removed** (carried over from Sprint 10's initial schema, dropped here):

- `deezer_album_id` (was for Deezer genre lookups; superseded)
- `preview_url` (Deezer previews expire; fetched on demand instead)
- `status` + `tracks_status_check` constraint (replaced by `classified_at IS NOT NULL`)
- `raw_genres` (was Deezer genres; switching taxonomy)
- `raw_artists` (collab attribution simplified to single primary artist; if needed later, a `track_collaborators` join table)
- `exclusion_reason` (excluded tracks are deleted, not flagged)

**Indexes:**

- HNSW on `mood_vector` (`vector_l2_ops`) — fast 3D nearest-neighbor for slider queries
- HNSW on `embedding` (`vector_cosine_ops`) — semantic similarity for "more like this" / scene anchoring

### Audio classification stack

Essentia + TensorFlow inference runs inside a Docker container (`essentia-tensorflow` ships linux/amd64 wheels only; runs via Rosetta on Apple Silicon hosts).

Two backbones compute embeddings once per 30s preview clip:

- **Effnet-Discogs** (1280-d) — carries genre + binary mood/timbre heads + the pooled track embedding
- **MusiCNN** (200-d) — carries the A/V regression heads (no Effnet variants published for those)

**Classifier heads** (multi-label tag-soup, on Effnet embedding):
- `genre_discogs400` (400 Discogs styles, top-K)
- `mtg_jamendo_moodtheme` (mood/theme tag soup)

**Binary classifiers** (on Effnet, probability of each class):
- `voice_instrumental`
- `danceability`
- `mood_happy`, `mood_sad`, `mood_aggressive`, `mood_relaxed`, `mood_party`
- `mood_electronic`, `mood_acoustic`, `nsynth_acoustic_electronic`
- `nsynth_bright_dark`, `timbre`
- `engagement_3c`, `approachability_3c`

**Regression heads** (continuous valence/arousal on MusiCNN, 1-9 DEAM scale):
- `deam`, `emomusic`, `muse`

**DSP features** (Essentia standard algorithms, 44.1 kHz):
- BPM + confidence (`RhythmExtractor2013`, multifeature)
- Key + scale + strength (`KeyExtractor`)
- Mean spectral centroid (Hann-windowed STFT → `Centroid`)

All raw outputs go into `features` JSONB. The derived `mood_vector` can be recomputed from JSONB without re-running Essentia — important since formula tuning will be iterative.

### 3D mood vector derivation

The product-facing axes (all clamped to `[-1, +1]`):

- **mood**: dark ↔ bright — *mix of timbral brightness and emotional valence*. Going to require some trials to get the formula right.
- **energy**: chill ↔ dynamic — arousal + danceability + tempo
- **instrumentation**: organic ↔ electronic — direct from the acoustic/electronic classifier heads

Lives in `app/services/mood_vector.py`. Weights are explicit constants and tunable without re-classifying. Inital mood formulas:

```
mood            = 0.55·centroid + 0.20·valence + 0.15·(happy − sad) + 0.10·mode_bonus
energy          = 0.50·arousal + 0.30·danceability + 0.20·normalized_bpm
instrumentation = 2·acoustic_electronic.electronic − 1
```

(POC exposed three candidate formulas — A/B/C — for spot-comparison across a small set of tracks. The chosen variant lands here; the JSONB lets us swap formulas later cheaply.)

### Streaming link resolution

For each classified track, store playback URLs via yt-dlp search prefixes:

- **YouTube**: `ytsearch1:` with `extract_flat='in_playlist'` — avoids format-selection errors on age-restricted/Premium-encoded videos. We only need the video ID; flat mode returns it along with title + duration.
- **SoundCloud**: `scsearch1:` with full extraction first. Falls back to flat-mode search when the SoundCloud metadata API returns 404 (common: scraped `client_id` rotation). Only accepts URLs whose host is `soundcloud.com` — never `api.soundcloud.com`.

**Match validation** (must pass all three to accept a candidate):

1. Duration within ±10s of `track.duration_ms`
2. Every meaningful word from the source title (after stripping `(Original Mix)`-style qualifiers and apostrophes) is present in the candidate's title
3. Concatenation-tolerant for 4+ char words ("Acid Pauli" matches "Acidpauli")

**Rate-limit handling**: detects `429` / `Too Many Requests` / `Sign in to confirm`, waits, retries once, stops cleanly on persistent throttling without marking tracks as attempted. 403s and per-track 404s are treated as normal "track unavailable" failures.

### Services

#### `ClassificationService` (`app/services/classification_service.py`)

Wraps the Essentia pipeline. Runs inside the essentia-tensorflow Docker container (cannot be invoked from the host directly):

- `classify_track(track_id, preview_source)` — run the full Essentia chain on a 30s clip fetched via the injected `preview_source` abstraction, derive the mood vector, persist to `features` / `embedding` / `classified_at` / `classifier_version`. Nothing else.
- `classify_artist(artist_id, preview_source)` — bulk-classify every unclassified track of one artist. Idempotent.

The preview-download logic is **not** owned by this service — it's an injected abstraction (e.g. `DeezerPreviewSource` calling the existing `DeezerClient`, or a future SoundCloud / yt-dlp source). Keeps the Essentia pipeline source-agnostic and the service focused on audio analysis only.

Designed to be callable from Celery tasks so the admin "add artist" flow can fan out classification work asynchronously.

#### `StreamingResolutionService` (`app/services/streaming_resolution_service.py`)

Wraps yt-dlp-based URL resolution. Runs natively (no Docker):

- `resolve_track(track_id)` — search both platforms, validate, persist URLs + `streaming_resolved_at`
- `resolve_artist(artist_id)` — bulk-resolve every unresolved track of one artist

Idempotent on `streaming_resolved_at IS NULL`. Rate-limit aware (one backoff + retry, then graceful stop preserving DB consistency).

#### `MoodVectorService` (`app/services/mood_vector.py`)

Pure-function module — no DB, no I/O:

- `derive(features: dict) -> (mood, energy, instrumentation)` — applies the formula to a JSONB-shaped dict
- Lets us recompute the entire catalog's `mood_vector` column from `features` after any formula change, in seconds, no Essentia needed

### Track import enrichment

Three columns are **not** populated by classification — they come from the track-ingestion side and need to be fetched at import time, once per track:

- `loudness_db` — Deezer's `gain` field (ReplayGain in dB)
- `release_date` — Deezer track release date
- `isrc` — when missing on insert

The existing track-ingestion flow (Sprint 10) is extended to fetch the Deezer track payload once at insert time and populate these. Could live as a small standalone service or fold into `DeezerClient`. The initial-backfill scripts did this fetch inside `classify_track` as a one-off convenience; going forward the responsibility moves to the import path so classification stays purely audio-analysis.

### Integration points

- **Admin "Add artist" flow** (Sprint 12): on artist creation, fan out classification + streaming-resolution Celery tasks scoped to that artist
- **Periodic backfill** (background Celery beat): every few hours, pick up tracks created since last run and process them
- **Admin manual triggers** (Sprint 12): "(re)classify this track" and "resolve streaming links" buttons per-track and per-artist

### Initial catalog backfill

Performed via one-time scripts (not committed to the repo — single-use, replaced by the services above for ongoing work):

- ~75k tracks classified via Essentia
- ~75-85% YouTube match rate (independent)
- ~50% SoundCloud match rate (independent — most tracks land with YT-only, some with both, some with neither)
- Artist names canonicalized against Deezer (2400+ corrections applied)

## Out of scope

- Tuning the mood formula against a large validation set — initial weights are POC-derived; refine later with labeled data
- Custom genre taxonomy decision (Discogs 400 vs Spotify artist genres) — kept in `features` JSONB for now, materialized to a typed column once decided
- SoundCloud `client_id` auto-rotation (yt-dlp handles it; revisit if 404 rate stays high)
- Public playlist generation queries on top of `mood_vector` / `embedding` (separate sprint)
- Manual artist-row merging tool for duplicate-name conflicts surfaced during name correction (small number; handled via psql)

## Done when

- Migrations 011, 012, 013 applied
- HNSW indexes built on `mood_vector` and `embedding`
- ~75k tracks have populated `features` + `embedding` + `mood_vector` + `classified_at`
- ~75k tracks have `streaming_resolved_at` set (whether or not URLs were found)
- `ClassificationService`, `StreamingResolutionService`, `MoodVectorService` all exist and are callable per-track and per-artist
- `ClassificationService` accepts an injected preview source (no Deezer coupling)
- Track-ingestion flow populates `loudness_db` / `isrc` / `release_date` at insert time (not via classification)
- Per-artist bulk operations are idempotent and Ctrl-C-resumable
- Raw `features` JSONB lets us re-derive `mood_vector` without re-running Essentia
