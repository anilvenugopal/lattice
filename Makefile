.PHONY: help setup dev migrate revision seed reset test lint format

help:  ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:  ## Install all workspace packages, migrate, seed development data
	uv sync --all-packages
	uv run lattice migrate
	uv run lattice seed

dev:  ## Run the host with reload on http://localhost:8000
	uv run lattice dev

migrate:  ## Apply pending migrations
	uv run lattice migrate

revision:  ## New migration from model changes: make revision m="add widget table"
	uv run alembic revision --autogenerate -m "$(m)" --rev-id $$(printf "%04d" $$(( $$(ls alembic/versions/[0-9]*.py | wc -l) + 1 )))

seed:  ## Add development users and each app's example data (skips if users exist)
	uv run lattice seed

reset:  ## DESTRUCTIVE: delete the SQLite development database, migrate and seed
	rm -f data/lattice.db data/lattice.db-wal data/lattice.db-shm
	uv run lattice migrate
	uv run lattice seed

test:  ## Run the test suite (core and apps)
	uv run pytest -q

lint:  ## Lint and check import contracts
	uv run ruff check .
	uv run lint-imports

format:  ## Fix lint issues that are safe to fix
	uv run ruff check . --fix
