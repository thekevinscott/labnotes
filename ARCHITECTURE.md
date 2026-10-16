# Architecture

A pure-Python CLI, built with hatchling and run with `uvx labnotes`.

## Packages

```
packages/
  python/    the labnotes package. Source and colocated tests in src/labnotes/.
docs/        VitePress site (published to GitHub Pages).
  internals/ contributor + agent conventions (not published).
```

## Release flow

`putitoutthere.toml` declares one PyPI package. The `Release` workflow
(`.github/workflows/release.yml`) calls the reusable workflow at
`thekevinscott/putitoutthere`. The version comes from git tags via
`hatch-vcs`. Release globs exclude `testing-conventions.toml`,
`changelog.d/`, `migrations.d/`, and `e2e-attestations/` bookkeeping.

## CI gates

- `python.yml` runs lint, test, type-check, and a wheel build with a `uvx` smoke test.
- [`conventions.yml`](.github/workflows/conventions.yml) calls the upstream [testing-conventions workflow](https://github.com/thekevinscott/testing-conventions/blob/v0/.github/workflows/testing-conventions.yml) at `v0`; its current coverage is described below.
- `changelog.yml` runs the upstream testing-conventions `changelog` gate: a fragment under `docs/changelog.d/` on PRs that touch package code, plus `docs/migrations.d/` when a commit carries a `breaking:` trailer.
- `workflow-lint.yml` runs the upstream testing-conventions `workflow-lint` gate, which fails on logic inlined in workflow YAML.
- `docs.yml` builds + deploys the VitePress site.
- `pr-monitor.yml` gates merge on the aggregate CI status.

Testing conventions cover colocated tests and source/test co-change, unit-test
isolation and mocking hygiene, one function per file, unit and changed-line
coverage, mutation testing on changed lines, integration-test layout, exclusion
of tests from built distributions, and E2E attestation freshness. Gates run
when applicable to the detected sources, distributions, and attestations.

The Python lane scans `packages/python` with upstream defaults.

The policy is upstream defaults, with no custom `testing-conventions.toml` or
exemptions.

## Public-API surface

Defined in `docs/internals/repo.md`: every exported value/type, every CLI
flag, every config key, every observable artifact. Changes to that
surface require a fragment under `docs/changelog.d/` (plus
`docs/migrations.d/` when breaking).
