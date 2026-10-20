set shell := ["bash", "-cu"]

default:
    @just --list

# ---- Python --------------------------------------------------------------

py-lint:
    cd packages/python && uv run ruff check . && uv run ruff format --check .

py-format:
    cd packages/python && uv run ruff check --fix . && uv run ruff format .

py-typecheck:
    cd packages/python && uv run mypy src

py-test:
    cd packages/python && uv run pytest

py-build:
    cd packages/python && uv build

# ---- Docs ----------------------------------------------------------------

docs-install:
    cd docs && pnpm install --no-frozen-lockfile

docs-dev:
    cd docs && pnpm run dev

docs-build:
    cd docs && pnpm run build

# ---- CI gates (testing-conventions) --------------------------------------

# Gate: fail if any workflow / composite-action YAML encodes a non-trivial
# inline script (docs/internals/repo.md). Run from the repo root.
gha-lint:
    uvx testing-conventions workflow-lint

# ---- Aggregates ----------------------------------------------------------

lint: py-lint gha-lint
format: py-format
typecheck: py-typecheck
test: py-test
build: py-build

ci: lint typecheck test

hooks:
    pre-commit install --install-hooks

clean:
    trash-put packages/python/dist docs/.vitepress/dist
