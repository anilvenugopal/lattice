.PHONY: help db-up db-down setup dev migrate migration seed reset maps test lint format

COMPOSE ?= podman-compose

help:  ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

db-up:  ## Start Postgres (compose.yaml, port 5436) and wait until it accepts connections
	$(COMPOSE) up -d
	@until pg_isready -q -h 127.0.0.1 -p 5436; do sleep 1; done; echo "Postgres is ready on 5436"

db-down:  ## Stop Postgres; the data stays in its volume
	$(COMPOSE) down

setup:  ## Install all workspace packages, migrate, seed development data
	uv sync --all-packages
	uv run lattice migrate
	uv run lattice seed

dev:  ## Run the host with reload on http://localhost:8000
	uv run lattice dev

migrate:  ## Apply pending migrations
	uv run lattice migrate

migration:  ## New migration file: make migration schema=showcase m="add ticket table"
	uv run lattice new-migration $(schema) "$(m)"

seed:  ## Add development users and each app's example data (skips if users exist)
	uv run lattice seed

reset:  ## DESTRUCTIVE: drop Lattice's and the apps' schemas, migrate and seed (not in production)
	uv run lattice reset

maps:  ## Download the self-hosted US basemap (about 400 MB) and its fonts; maps work without it
	scripts/maps.sh

test:  ## Run the test suite (core and apps)
	uv run pytest -q

lint:  ## Lint and check import contracts
	uv run ruff check .
	uv run lint-imports

format:  ## Fix lint issues that are safe to fix
	uv run ruff check . --fix
