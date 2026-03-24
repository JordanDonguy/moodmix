# Sprint 8 — Celery Task Queue

**Goal:** Replace APScheduler with Celery + Redis for production-grade background job processing.

**Depends on:** Sprint 7 (Redis already running)

## Tasks

### 8.1 — Celery setup
- [ ] Add `celery[redis]` to dependencies
- [ ] `app/tasks/celery_app.py` — Celery app instance
  - Broker: Redis (same instance as cache, different DB number or same)
  - Result backend: Redis
  - Task serialization: JSON
  - Configure timezone, task discovery

### 8.2 — Define Celery tasks
- [ ] `app/tasks/pipeline_tasks.py`:
  - `crawl_channels_task()` — calls `CrawlerService.crawl_channel()` for all active seed channels
  - `crawl_keywords_task()` — picks N queries from rotating list, calls `CrawlerService.search_keywords()`
  - `classify_pending_task()` — calls `ClassifierService.classify_pending_batch()`
  - `check_availability_task()` — calls `CrawlerService.check_availability()` on random batch
- [ ] Each task:
  - Creates a `pipeline_run` record at start (status: running)
  - Updates it on completion (status: completed, mixes_processed, mixes_added)
  - Updates it on failure (status: failed, error_message)
  - Invalidates Redis cache if catalog changed

### 8.3 — Celery Beat schedule
- [ ] Configure Celery Beat schedule in `celery_app.py`:
  ```python
  beat_schedule = {
      'crawl-channels-weekly': {
          'task': 'app.tasks.pipeline_tasks.crawl_channels_task',
          'schedule': crontab(day_of_week=0, hour=2),  # Sunday 2 AM
      },
      'crawl-keywords-daily': {
          'task': 'app.tasks.pipeline_tasks.crawl_keywords_task',
          'schedule': crontab(hour=3),  # Daily 3 AM
      },
      'classify-pending-daily': {
          'task': 'app.tasks.pipeline_tasks.classify_pending_task',
          'schedule': crontab(hour=4),  # Daily 4 AM
      },
      'check-availability-daily': {
          'task': 'app.tasks.pipeline_tasks.check_availability_task',
          'schedule': crontab(hour=5),  # Daily 5 AM
      },
  }
  ```

### 8.4 — Remove APScheduler
- [ ] Remove APScheduler dependency and `app/tasks/scheduler.py`
- [ ] All scheduling now goes through Celery Beat

### 8.5 — Update admin endpoints
- [ ] `POST /api/admin/crawl/trigger` now enqueues a Celery task:
  ```python
  task = crawl_channels_task.delay()
  return { "task_id": task.id, "message": "Task enqueued" }
  ```
- [ ] Return 202 (Accepted) instead of waiting for completion

### 8.6 — Update docker-compose
- [ ] Add `worker` and `beat` services:
  ```yaml
  worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    env_file: .env
  beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    env_file: .env
  ```
- [ ] All 3 services (api, worker, beat) share the same image, different entrypoints

### 8.7 — Test
- [ ] Start all services: `docker compose up`
- [ ] Trigger a crawl via admin endpoint → verify task appears in worker logs
- [ ] Wait for scheduled task → verify pipeline_run record created
- [ ] Verify mixes appear in DB after crawl + classify tasks run

## Done when

- [ ] `docker compose ps` shows 4 healthy services: api, worker, beat, redis
- [ ] Celery worker logs show tasks being processed
- [ ] Celery Beat fires tasks on schedule
- [ ] Admin trigger endpoint returns 202 + task_id
- [ ] Pipeline runs table populated by Celery tasks
- [ ] APScheduler fully removed
