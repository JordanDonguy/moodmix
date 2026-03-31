# Sprint 2 — Data Pipeline

**Goal:** Crawl YouTube mixes into the DB and classify the initial seed catalog.

**Depends on:** Sprint 1 (DB tables exist, models defined)

## PR 2a — Crawler service + admin endpoints ✅

### 2.1 — YouTube crawler service 
- [x] `app/services/youtube_client.py` — low-level YouTube Data API client
- [x] `app/services/crawler_service.py` — orchestrates crawling + DB storage
- [x] Methods: `crawl_channel`, `search_and_crawl`, `check_availability`
- [x] Chapter parsing from description + fallback from comments
- [x] Skip duplicates (ON CONFLICT DO NOTHING)
- [x] Skip videos < 1,000 views, < 20min, not embeddable
- [x] Quota tracking

### 2.2 — Seed channels + admin 
- [x] `data/seed_channels.json` + `scripts/import_seed_channels.py`
- [x] `POST /api/admin/crawl/channel` + `POST /api/admin/crawl/search` (API key protected)
- [x] `make seed-channels` command

## PR 2b — Admin review tooling ✅

### 2.3 — Skipped videos tracking
- [x] `skipped_videos` table — stores youtube_ids we crawled but filtered out (too short, low views, not embeddable)
- [x] `reason` column for why it was skipped
- [x] Crawler checks both `mixes` and `skipped_videos` when filtering existing — enables early stop when a full page is all known

### 2.4 — Mix validation field
- [x] Add `validated` boolean to `mixes` model (default false)
- [x] Only validated mixes are served to frontend users
- [x] Migration to add the column

### 2.5 — SQLAdmin panel
- [x] Set up SQLAdmin at `/admin`
- [x] Register Mix, SeedChannel, Genre models
- [x] Clickable YouTube links in mix list view
- [x] Inline editing of mood, energy, instrumentation, genres, has_vocals, validated

## PR 2c — Initial crawl run
- [x] Run crawler on all seed channels
- [x] Verify: mixes appear in `mixes` table with `mood_vector = NULL` (pending classification)
- [x] Target: ~1,000 unclassified mixes

## PR 2d — Classification pipeline

### 2.6 — Export for Claude Code classification
- [x] Write a script that exports pending mixes as JSON:
  ```json
  [
    {
      "id": "uuid",
      "youtube_id": "abc123",
      "title": "...",
      "channel_name": "...",
      "description": "...",
      "tags": ["..."],
      "thumbnail_url": "..."
    }
  ]
  ```
- [x] Export to `data/pending_mixes_batch_001.json` (batches of ~50-100)
- [x] Include thumbnail_url — used by Claude Code for mood classification (dark/bright axis)

### 2.7 — Claude Code classification (manual, batched)
- [x] Open Claude Code, feed it a batch JSON
- [x] Prompt includes: title, channel, description, tags, thumbnail image
- [x] Output: classified JSON with mood vectors, genres, has_vocals, confidence
- [x] Repeat for all batches until initial seed is classified

### 2.6 — Import classified results
- [x] Write a script that reads classified JSON and updates mixes in DB:
  - Set mood_vector, mood, energy, instrumentation, has_vocals, classification_confidence
  - Insert into mix_genres (lookup genre by slug)
- [x] Verify: spot-check 20 random mixes for reasonable values

**Files created:**
```
scripts/import_classified.py
```

### 2.7 — Audio-based chapter detection (for mixes without tracklists)
- [ ] Script: `scripts/detect_chapters_audio.py`
- [ ] Download audio stream via `yt-dlp` (audio only, temporary)
- [ ] Analyze with `pydub` or `librosa` for volume drops / silence gaps
- [ ] Filter: minimum 2m30s between detected chapters
- [ ] Store as chapters with generic titles ("Track 1", "Track 2", etc.)
- [ ] Run on the ~600 mixes that have no chapters from description or comments
- [ ] Cleanup: delete downloaded audio after processing

**Note:** Doesn't need to be perfect — "good enough" chapters let users skip tracks they don't like, even if boundaries aren't exact. Run before frontend launch.

## Done when

- [x] Seed channels are in DB
- [x] Initial crawl produces 2,000+ mixes in `mixes` table
- [x] Claude Code classification completes on initial seed
- [x] Import script populates mood_vector, genres, has_vocals for all classified mixes
- [x] Automated classifier works on a test batch of 10 pending mixes
- [x] Scheduler runs without errors (test each job manually first)
- [ ] `pipeline_runs` table has entries for each job type
