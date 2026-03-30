# Sprint 6 — Deployment

**Goal:** App running on Hetzner VPS, accessible via HTTPS, with CI/CD pipeline.

**Depends on:** Sprint 5 (frontend + backend both working locally)

## Tasks

### 6.1 — Backend Dockerfile
- [ ] `backend/Dockerfile` — multi-stage:
  ```
  Stage 1: python:3.12-slim — install deps via uv/pip
  Stage 2: copy app code, expose port 8000
  CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- [ ] `.dockerignore` — exclude `.env`, `__pycache__`, tests, data/
- [ ] Build and test locally: `docker build -t moodmix-api ./backend`

### 6.2 — Docker Compose
- [ ] `docker-compose.yml` at project root:
  ```yaml
  services:
    api:
      build: ./backend
      ports: ["8000:8000"]
      env_file: .env
    redis:
      image: redis:7-alpine
      ports: ["6379:6379"]
  ```
  (Celery worker + beat added in sprint 8)
- [ ] Test locally: `docker compose up` → API accessible at localhost:8000

### 6.3 — Frontend build
- [ ] `frontend/Dockerfile` (optional — or just build static files)
- [ ] `npm run build` → `dist/` folder with static files
- [ ] Configure Vite to use production API URL via env var

### 6.4 — nginx configuration
- [ ] Create nginx config for VPS:
  ```
  server {
      server_name moodmix.yourdomain.com;

      # Frontend static files
      location / {
          root /var/www/moodmix/frontend;
          try_files $uri $uri/ /index.html;
      }

      # API reverse proxy
      location /api/ {
          proxy_pass http://localhost:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      }
  }
  ```
- [ ] SSL via certbot: `certbot --nginx -d moodmix.yourdomain.com`

### 6.5 — GitHub Actions CI/CD
- [ ] `.github/workflows/deploy.yml`:
  - **Trigger:** push to `main`
  - **Test job:** checkout → setup Python → install deps → run `pytest`
  - **Build job:** (depends on test) build Docker image → push to ghcr.io
  - **Deploy job:** (depends on build) SSH into VPS → pull new image → `docker compose up -d`
- [ ] Store VPS SSH key + credentials as GitHub secrets
- [ ] Store `.env` values as GitHub secrets or manage on VPS directly

### 6.6 — Frontend deployment
- [ ] Option A: serve from nginx on VPS (copy `dist/` to `/var/www/moodmix/frontend/`)
- [ ] Option B: deploy to Vercel/Netlify free tier
- [ ] Add frontend build + deploy step to GitHub Actions pipeline
- [ ] Either way: configure production `VITE_API_URL` to point to the VPS API

### 6.7 — Production .env setup
- [ ] Create `.env` on VPS with production values:
  - Supabase connection string
  - YouTube API key
  - LLM API key
  - Admin API key
  - CORS origins (production frontend URL)
- [ ] Verify: `.env` is NOT in the repo

### 6.8 — Smoke test
- [ ] Hit `https://moodmix.yourdomain.com` → frontend loads
- [ ] Hit `https://moodmix.yourdomain.com/api/health` → healthy response
- [ ] Test full flow: sliders → results → play mix

### 6.9 — Automated classifier service (for ongoing catalog growth)
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

> **Pattern: Strategy** — Swapping LLM providers (Haiku ↔ GPT-120B ↔ future models) requires zero changes to `ClassifierService` or any calling code. Just add a new strategy class and update config.
>
> **Pattern: Dependency Injection** — `ClassifierService` receives its strategy via constructor, not by instantiating it internally. Makes testing trivial (inject a mock strategy).

### 6.10 — Pipeline scheduler (APScheduler for now, Celery later in sprint 8)
- [ ] `app/tasks/scheduler.py` — APScheduler setup
- [ ] Scheduled jobs:
  - Weekly: crawl all active seed channels
  - Daily: run 30 keyword searches from a rotating query list
  - Daily: check availability on random 200 mixes
  - Daily: classify all pending mixes
- [ ] Log each run to `pipeline_runs` table

## Done when

- [ ] `https://moodmix.yourdomain.com` serves the frontend
- [ ] API responds behind HTTPS
- [ ] Push to `main` triggers: test → build → deploy automatically
- [ ] Docker containers running on VPS (`docker compose ps` shows api + redis healthy)
