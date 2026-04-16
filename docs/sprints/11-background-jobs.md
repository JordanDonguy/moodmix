# Sprint 11 — Background Jobs (Celery + Redis broker)

**Goal:** Scheduled crawl, classification, availability checks, and analytics generation via Celery — replacing manual scripts.

**Depends on:** Sprint 10 (analytics task is one of the scheduled jobs)

## Scope

### Infrastructure
- Add Redis service to `docker-compose.prod.yml` (broker + result backend; not yet used for caching)
- Add `worker` and `beat` services running Celery
- Wire shared config + DB connection into worker

### Tasks
- `crawl_channels` — periodic seed channel crawl
- `classify_pending` — classify any unclassified mixes
- `check_availability` — flag YouTube videos that became unavailable
- `generate_analytics_report` — scheduled report snapshot

### Beat schedule
- Daily: crawl + classify
- Weekly: availability check + analytics report
- Cadence configurable via env vars

### Observability
- Each task writes to existing `pipeline_runs` table on start/complete/fail
- Admin dashboard surfaces recent runs with status, duration, error message
- Manual trigger button per task in admin dashboard

## Out of scope

- Redis caching (separate sprint, deferred)
- Distributed workers / autoscaling (single worker is fine at current load)
- Celery Flower or similar monitoring UI (defer until needed)

## Decisions to make during impl

- Retry strategy per task (exponential backoff, max attempts)
- Should `check_availability` be batched (e.g., 50 mixes per task invocation) or one task per mix?
- Beat container vs cron-triggered task — Celery Beat is the obvious choice but adds a service

## Done when

- Beat fires scheduled tasks without manual intervention
- Admin can manually kick off any task and see the result
- Failures retry with backoff; final failures surface in admin UI with stack trace
- No more manually-run scripts in the catalog growth loop
