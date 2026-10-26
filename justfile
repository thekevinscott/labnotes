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
    cd packages/python && uv run pytest src/labnotes tests/integration

# Drives a real `claude` (installed, on PATH) with the mod loaded.
py-e2e:
    cd packages/python && uv run pytest tests/e2e

py-build:
    cd packages/python && uv build

# ---- Pane ----------------------------------------------------------------

# Lays the types Claude Code generates, then type-checks the mod.
pane-typecheck:
    python3 scripts/pane_types.py
    pnpm --package=typescript@5.9.3 dlx tsc --noEmit -p skills/labnotes

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
