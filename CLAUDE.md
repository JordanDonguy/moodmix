# MoodMix — Claude Code Guidelines

## Project Overview

Background music discovery app. Users find 1-hour YouTube mixes via mood sliders, genre filters, and AI search. Built with FastAPI + React + PostgreSQL (pgvector).

## Monorepo Structure

```
moodmix/
├── backend/       — FastAPI (Python 3.14, uv)
├── frontend/      — React (Vite + TypeScript)
├── docs/          — Architecture, schema, sprints, API routes
└── Makefile       — Dev commands (make dev, make migrate, make test, etc.)
```

## Commands

- `make dev` — Start backend with hot reload
- `make migrate` — Run Alembic migrations
- `make db-up` / `make db-down` — Start/stop local Postgres (pgvector, port 5433)
- `make test` — Run pytest
- `make install` — Install backend dependencies

## Commit Conventions

- **One-liner messages**, imperative mood ("add", "fix", not "added", "fixes")
- **Atomic commits** — one logical change per commit
- **Conventional commits** with scope:
  - `feat(crawler): add keyword search discovery`
  - `fix(search): handle empty genre filter`
  - `chore(deps): update fastapi to 0.136`
  - `test(classifier): add unit tests for mood vector output`
  - `docs(api): document ai-search endpoint`

## Code Quality

- Apply **SOLID principles** throughout — clean separation of concerns, extensible code, no god classes.
- Use **design patterns** wherever they naturally fit (DI, strategy, repository, DTOs) — but never force a pattern where simple code does the job.
- **Type hints** on all function signatures.
- `async` for all I/O-bound operations (DB, HTTP calls).
- No bare `except:` — always catch specific exceptions.

### Backend Architecture

```
routers/    → Request handling, validation, response shaping
services/   → Business logic, external API calls
models/     → SQLAlchemy ORM models (DB schema)
schemas/    → Pydantic models (API contracts)
tasks/      → Celery background tasks
middleware/ — Auth, rate limiting
```

Routers call services, services call the DB or external APIs. Never skip layers.
