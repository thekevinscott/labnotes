# Agent contract

This file is the operating contract for AI agents working in this repo.
Conventions, supervision rules, and per-language style live under
`docs/internals/` — start there before making changes.

## Where to read first

- `docs/internals/repo.md` — cross-cutting rules (changelog/migration fragment philosophy, public-API surface, CI-logic-in-scripts).
- `docs/AGENTS.md` — what the docs site holds and what stays out of the build.
- `docs/internals/python/` — Python style, testing, shipping, review, setup.

## Package layout

- `packages/` holds public-facing packages published to a registry.
- `internals/` holds internal-only packages, built and tested to the same
  standards but never published. Private workspaces that only produce build
  artifacts for a published package belong here too.

## Workflow

- Use `just` for local tasks (`just lint`, `just test`, `just ci`).
- Unit tests are **colocated** with their source (`foo.py` ↔ `foo_test.py`). This is the
  [testing-conventions](https://github.com/thekevinscott/testing-conventions)
  standard, enforced in CI by `.github/workflows/conventions.yml`.
- **CI logic lives in scripts, not workflow YAML.** `run:` / `github-script`
  steps stay trivial glue; anything with iteration, `case` dispatch, or
  text-munging moves to a tested script invoked as a one-liner. A gate more
  than one repo needs belongs upstream in the tool that owns it
  (testing-conventions, putitoutthere, pr-monitor), not in a repo-local
  package. Enforced by testing-conventions' `workflow-lint` check
  (`.github/workflows/workflow-lint.yml`); the bright line and rationale are in
  `docs/internals/repo.md`.
- Every PR that changes a public API adds a **changelog fragment**: one
  timestamped file under `docs/changelog.d/` (plus one under
  `docs/migrations.d/` for breaking changes), named `YYYY-MM-DD-<pkg>-<slug>.md`
  by UTC merge date. The folders are the permanent, append-only record;
  `packages/<pkg>/CHANGELOG.md` / `MIGRATIONS.md` are pointer stubs — never
  append entries to them. For version attribution ("which release shipped X"),
  map fragment dates against tags via `git log --tags`. Enforced by
  testing-conventions' `changelog` check (`.github/workflows/changelog.yml`).
  Two git trailers steer it: `skip-changelog: <reason>` bypasses the check for
  genuinely internal refactors, and `breaking: <reason>` marks a breaking
  change, which then also requires the `docs/migrations.d/` fragment.
- Pre-commit hooks (`just hooks` to install) gate formatting, gitleaks, and ruff.
- Remove a worktree as soon as its PR merges or its branch is abandoned; don't
  ask first. Check for uncommitted work, `cd` to the repo root, then
  `git worktree remove <path>`. Stale worktrees under `.worktrees/` and
  `.claude/worktrees/` pin branches and block `gh pr merge --delete-branch`.

## First-publish prerequisites

Before the first `Release` run on a fresh scaffold:

1. **Repo must be public.** PyPI Trusted Publishing requires the provider
   to inspect the workflow file at the configured ref; private repos cannot
   satisfy this. The `preflight` job in `.github/workflows/release.yml`
   fails fast if the repo is private.
2. **Register a pending Trusted Publisher on PyPI** for `labnotes`
   (workflow `release.yml`, environment `release`). PyPI allows this before
   the project exists, so no token is needed. putitoutthere's
   [first-release guide](https://github.com/thekevinscott/putitoutthere/blob/main/.claude/skills/first-release/reference/trusted-publishers.md)
   has the steps.

## Out of scope

- Don't add unsolicited refactors or hypothetical-future abstractions.
- Don't bypass hooks or CI gates without an explicit reason in the PR body.

@docs/internals/session-handoff.md
