# Sprint 2 — Data Pipeline

**Goal:** Crawl YouTube mixes into the DB and classify the initial seed catalog.

**Depends on:** Sprint 1 (DB tables exist, models defined)

## Tasks

### 2.1 — YouTube crawler service
- [ ] `app/services/crawler_service.py`
- [ ] `CrawlerService` class with `httpx.AsyncClient`
- [ ] Methods:
  - `crawl_channel(channel_id: str)` — fetch uploads playlist → filter by duration >= 30min + embeddable → insert into `mixes` table
  - `search_keywords(query: str)` — `search.list` with `videoDuration=long`, `videoCategoryId=10` → filter + insert
  - `check_availability(mix_ids: list[uuid])` — batch `videos.list` → mark unavailable ones
- [ ] For each discovered video, extract and store:
  - youtube_id, title, channel_name, channel_id, description, tags, duration_seconds, thumbnail_url, published_at, view_count
- [ ] Skip duplicates (ON CONFLICT youtube_id DO NOTHING)
- [ ] Skip videos with < 1,000 views
- [ ] Log quota usage per call

> **Pattern: Single Responsibility** — `CrawlerService` only discovers and stores raw YouTube metadata. It does not classify. Classification is a separate service with its own responsibility.

### 2.2 — Seed channels list
- [ ] Create `data/seed_channels.json` with ~50-100 known channels:
  - Channel ID + name for: Lofi Girl, Chillhop, relaxdaily, Cafe Music BGM, Yellow Brick Cinema, etc.
- [ ] Write a script/endpoint to bulk-import seed channels into `seed_channels` table
- [ ] Each channel entry includes `uploads_playlist_id` (derive from channel ID: replace `UC` prefix with `UU`)

**Files created:**
```
data/seed_channels.json
```

### 2.3 — Initial crawl run
- [ ] Run crawler on all seed channels (can be a temporary CLI script or admin endpoint)
- [ ] Verify: mixes appear in `mixes` table with `mood_vector = NULL` (pending classification)
- [ ] Target: 2,000-5,000 unclassified mixes

### 2.4 — Export for Claude Code classification
- [ ] Write a script that exports pending mixes as JSON:
  ```json
  [
    {
      "id": "uuid",
      "youtube_id": "abc123",
      "title": "...",
      "channel_name": "...",
      "description": "...",
      "tags": ["..."]
    }
  ]
  ```
- [ ] Export to `data/pending_mixes_batch_001.json` (batches of ~50-100)

**Files created:**
```
scripts/export_pending.py
data/pending_mixes_batch_001.json  (generated)
```

### 2.5 — Claude Code classification (manual, batched)
- [ ] Open Claude Code, feed it a batch JSON
- [ ] Prompt it with the classification prompt from the plan
- [ ] Output: classified JSON with mood vectors, genres, has_vocals, confidence
- [ ] Repeat for all batches until initial seed is classified

### 2.6 — Import classified results
- [ ] Write a script that reads classified JSON and updates mixes in DB:
  - Set mood_vector, valence, energy, instrumentation, has_vocals, classification_confidence
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
