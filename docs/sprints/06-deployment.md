# Sprint 6 — Deployment

**Goal:** App running on Hetzner VPS, accessible via HTTPS, with CI/CD pipeline.

**Depends on:** Sprint 5 (testing complete, backend + frontend working locally)

## Tasks

### 6.1 — Backend Dockerfile
- [x] `backend/Dockerfile` — multi-stage build:
  - Stage 1 (builder): `python:3.14-slim` + `build-essential` (asyncpg C extensions) + uv dependency install (`--no-dev`)
  - Stage 2 (runtime): slim image, copies `.venv` from builder, non-root `appuser`, exposes port 8000
- [x] `backend/Dockerfile.test` — standalone single-stage build with all deps (including dev), runs migrations + pytest
- [x] `backend/.dockerignore` — excludes `.venv`, `__pycache__`, `.env*`, `scripts/`, `data/`, `.coverage`

### 6.2 — Docker Compose
- [x] `docker-compose.prod.yml`:
  - `db`: pgvector/pgvector:pg17, healthcheck, persistent volume, `POSTGRES_PASSWORD` from `.env`
  - `api`: builds from `./backend`, `env_file: ./backend/.env.prod`, bound to `127.0.0.1:8000`
- [x] `docker-compose.test.yml` updated:
  - `db-test`: pgvector/pgvector:pg17, healthcheck
  - `test`: builds from `Dockerfile.test`, `DATABASE_URL` overridden for Docker network (`db-test:5432`)

### 6.3 — Frontend deployment
- [x] Deployed to Cloudflare Pages
- [x] Production `VITE_API_URL` points to `https://api.moodmix.fm`

### 6.4 — nginx + SSL
- [x] nginx reverse proxy on VPS: `api.moodmix.fm` → `127.0.0.1:8000`
- [x] SSL via Cloudflare proxy (Full mode) + self-signed cert on VPS
- [x] Cloudflare DNS: A record `api` → VPS IP (proxied)
- [x] Admin panel (`/admin/`) protected with sqladmin `AuthenticationBackend` (password = `ADMIN_API_KEY`)
- [x] Cloudflare WAF rate limit on `/admin/login` (2 req/10s per IP)

### 6.5 — GitHub Actions CI/CD
- [x] `.github/workflows/test.yml`:
  - Triggers on push/PR to `main` (path-filtered to `backend/**`, `docker-compose.test.yml`, workflow file)
  - Runs tests entirely in Docker: `docker compose -f docker-compose.test.yml run --rm --build test`
- [x] `.github/workflows/deploy.yml`:
  - Triggers via `workflow_run` after Test workflow passes on `main`
  - Uses `appleboy/ssh-action` → VPS `moodmix` user → `command=` restriction runs `deploy.sh`
- [x] GitHub secrets: `DEPLOY_SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`

### 6.6 — VPS user + SSH setup
- [x] `moodmix` user with `/bin/bash`, restricted sudoers (docker commands only)
- [x] `moodmix_deploy` SSH key with `command=` restriction in `authorized_keys` (forces `deploy.sh`, no PTY/port forwarding)
- [x] Repo cloned at `/srv/moodmix`

### 6.7 — Deploy script
- [x] `deploy.sh` at repo root (executable `100755`):
  - `git pull` → backup current image as `:backup` → build new image
  - Run migrations in temp container (`docker compose run --rm api alembic upgrade head`)
  - Success: bring up new containers + prune old images
  - Failure: rollback to backup image, `exit 1` (fails the GH Action)

### 6.8 — Production environment
- [x] `/srv/moodmix/.env` with `POSTGRES_PASSWORD` (read by docker-compose variable substitution)
- [x] `/srv/moodmix/backend/.env.prod` with `DATABASE_URL` (host = `db`, not `localhost`), API keys, CORS origins
- [x] `.env` files NOT in repo (gitignored)

### 6.9 — Smoke test
- [x] `https://api.moodmix.fm/api/health` responds healthy
- [x] Admin panel requires login at `/admin/`
- [x] DB seeded from local dump (`pg_dump --data-only` → `TRUNCATE CASCADE` → restore)

## Deferred to future sprints

- **Classifier service** (strategy pattern, LLM-based classification) → Sprint 7
- **Pipeline scheduler** (APScheduler/Celery, crawl + classify + availability checks) → Sprint 8

## Done when

- [x] `https://moodmix.fm` serves the frontend (Cloudflare Pages)
- [x] API responds behind HTTPS at `https://api.moodmix.fm`
- [x] Push to `main` triggers: test → deploy automatically
- [x] Docker containers running on VPS (`docker compose ps` shows db + api healthy)
- [x] Admin panel protected (auth + rate limiting)
