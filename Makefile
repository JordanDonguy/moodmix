# Backend commands (run from project root)
dev:
	cd backend && uv run uvicorn app.main:app --reload --reload-dir app

migrate:
	cd backend && uv run alembic upgrade head

db-up:
	docker compose -f docker-compose.dev.yml up -d

db-down:
	docker compose -f docker-compose.dev.yml down

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

seed-channels:
	cd backend && uv run python scripts/import_seed_channels.py
