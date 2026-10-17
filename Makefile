.PHONY: help setup dev migrate revision seed reset test lint format

help:  ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:  ## Install dependencies, migrate, seed development data
	uv sync --all-packages
	uv run alembic upgrade head
	uv run python -m lattice_demo.seed

dev:  ## Run the app with reload on http://localhost:8000
	uv run uvicorn demo_host.main:app --reload --port 8000

migrate:  ## Apply pending migrations
	uv run alembic upgrade head

revision:  ## New migration from model changes: make revision m="add widget table"
	uv run alembic revision --autogenerate -m "$(m)" --rev-id $$(printf "%04d" $$(( $$(ls alembic/versions/[0-9]*.py | wc -l) + 1 )))

seed:  ## Add development users and example rows (skips if users exist)
	uv run python -m lattice_demo.seed

reset:  ## DESTRUCTIVE: delete the SQLite database, migrate and seed
	rm -f data/app.db data/app.db-wal data/app.db-shm
	uv run alembic upgrade head
	uv run python -m lattice_demo.seed

test:  ## Run the test suite
	uv run pytest -q

lint:  ## Lint
	uv run ruff check .

format:  ## Fix lint issues that are safe to fix
	uv run ruff check . --fix
