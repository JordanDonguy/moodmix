# Sprint 2 — Data Pipeline

**Goal:** Crawl YouTube mixes into the DB and classify the initial seed catalog.

**Depends on:** Sprint 1 (DB tables exist, models defined)

## PR 2a — Crawler service + admin endpoints (done)

### 2.1 — YouTube crawler service ✅
- [x] `app/services/youtube_client.py` — low-level YouTube Data API client
- [x] `app/services/crawler_service.py` — orchestrates crawling + DB storage
- [x] Methods: `crawl_channel`, `search_and_crawl`, `check_availability`
- [x] Chapter parsing from description + fallback from comments
- [x] Skip duplicates (ON CONFLICT DO NOTHING)
- [x] Skip videos < 1,000 views, < 20min, not embeddable
- [x] Quota tracking

### 2.2 — Seed channels + admin ✅
- [x] `data/seed_channels.json` + `scripts/import_seed_channels.py`
- [x] `POST /api/admin/crawl/channel` + `POST /api/admin/crawl/search` (API key protected)
- [x] `make seed-channels` command

## PR 2b — Admin review tooling (next)

### 2.3 — Skipped videos tracking
- [ ] `skipped_videos` table — stores youtube_ids we crawled but filtered out (too short, low views, not embeddable)
- [ ] `reason` column for why it was skipped
- [ ] Crawler checks both `mixes` and `skipped_videos` when filtering existing — enables early stop when a full page is all known

### 2.4 — Mix validation field
- [ ] Add `validated` boolean to `mixes` model (default false)
- [ ] Only validated mixes are served to frontend users
- [ ] Migration to add the column

### 2.5 — SQLAdmin panel
- [ ] Set up SQLAdmin at `/admin`
- [ ] Register Mix, SeedChannel, Genre models
- [ ] Clickable YouTube links in mix list view
- [ ] Inline editing of mood, energy, instrumentation, genres, has_vocals, validated

### 2.3 — Initial crawl run
- [ ] Run crawler on all seed channels
- [ ] Verify: mixes appear in `mixes` table with `mood_vector = NULL` (pending classification)
- [ ] Target: ~1,000 unclassified mixes

## PR 2c — Classification pipeline

### 2.6 — Export for Claude Code classification
- [ ] Write a script that exports pending mixes as JSON:
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
- [ ] Export to `data/pending_mixes_batch_001.json` (batches of ~50-100)
- [ ] Include thumbnail_url — used by Claude Code for mood classification (dark/bright axis)

### 2.7 — Claude Code classification (manual, batched)
- [ ] Open Claude Code, feed it a batch JSON
- [ ] Prompt includes: title, channel, description, tags, thumbnail image
- [ ] Output: classified JSON with mood vectors, genres, has_vocals, confidence
- [ ] Repeat for all batches until initial seed is classified

### 2.6 — Import classified results
- [ ] Write a script that reads classified JSON and updates mixes in DB:
  - Set mood_vector, mood, energy, instrumentation, has_vocals, classification_confidence
  - Insert into mix_genres (lookup genre by slug)
- [ ] Verify: spot-check 20 random mixes for reasonable values

**Files created:**
```
scripts/import_classified.py
```

### 2.7 — Automated classifier service
- [ ] `app/services/classifier_service.py`
- [ ] Define a `ClassifierStrategy` protocol (abstract interface):
  ```python
  class ClassifierStrategy(Protocol):
      async def classify(self, metadata: MixMetadata) -> ClassificationResult: ...
  ```
- [ ] `HaikuClassifier(ClassifierStrategy)` — calls Claude Haiku API
- [ ] `GptOssClassifier(ClassifierStrategy)` — calls OpenAI OSS GPT-120B API
- [ ] `ClassifierService` class takes a `ClassifierStrategy` via constructor injection
- [ ] `classify_mix(mix: Mix) -> ClassificationResult` — delegates to the strategy, parses JSON response
- [ ] `classify_pending_batch(batch_size: int = 50)` — fetch unclassified mixes, classify each, update DB
- [ ] Handle LLM response validation (check ranges, check genre slugs exist)
- [ ] Handle LLM errors gracefully (retry once, then skip and log)
- [ ] Which strategy to use is determined by `settings.LLM_PROVIDER` config value

> **Pattern: Strategy** — Swapping LLM providers (Haiku ↔ GPT-120B ↔ future models) requires zero changes to `ClassifierService` or any calling code. Just add a new strategy class and update config. This is also **Open/Closed** — open for extension (new providers), closed for modification.
>
> **Pattern: Dependency Injection** — `ClassifierService` receives its strategy via constructor, not by instantiating it internally. Makes testing trivial (inject a mock strategy).

### 2.8 — Pipeline scheduler (APScheduler for now, Celery later in sprint 8)
- [ ] `app/tasks/scheduler.py` — APScheduler setup
- [ ] Scheduled jobs:
  - Weekly: crawl all active seed channels
  - Daily: run 30 keyword searches from a rotating query list
  - Daily: check availability on random 200 mixes
  - Daily: classify all pending mixes
- [ ] Log each run to `pipeline_runs` table

**Files created:**
```
app/services/crawler_service.py
app/services/classifier_service.py
app/tasks/scheduler.py
data/keyword_queries.json
```

## Done when

- [ ] Seed channels are in DB
- [ ] Initial crawl produces 2,000+ mixes in `mixes` table
- [ ] Claude Code classification completes on initial seed
- [ ] Import script populates mood_vector, genres, has_vocals for all classified mixes
- [ ] Automated classifier works on a test batch of 10 pending mixes
- [ ] Scheduler runs without errors (test each job manually first)
- [ ] `pipeline_runs` table has entries for each job type
