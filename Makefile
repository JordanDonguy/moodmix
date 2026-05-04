# Backend commands (run from project root)
dev:
	cd backend && uv run uvicorn app.main:app --reload --reload-dir app

migrate:
	cd backend && uv run alembic upgrade head

db-up:
	docker compose -f docker-compose.dev.yml up -d

db-down:
	docker compose -f docker-compose.dev.yml down

db-restore-from-remote:
	./restore-from-remote.sh

test:
	cd backend && ENV_FILE=.env.test uv run pytest --cov=app --cov-report=term-missing

test-db-up:
	docker compose -f docker-compose.test.yml up -d

test-db-down:
	docker compose -f docker-compose.test.yml down

test-migrate:
	cd backend && ENV_FILE=.env.test uv run alembic upgrade head

install:
	cd backend && uv sync

# Audit Python deps for known vulnerabilities (PyPI advisory + OSV).
# `uvx` runs pip-audit in a throwaway env so we don't add it to project deps.
# Process substitution feeds the venv's installed-deps list to pip-audit
# without writing a temp file — uv-managed venvs don't ship with pip itself,
# so `pip-audit` can't introspect the env directly.
audit: SHELL := /bin/bash
audit:
	cd backend && uvx pip-audit -r <(uv pip freeze)

seed-channels:
	cd backend && uv run python scripts/import_seed_channels.py
