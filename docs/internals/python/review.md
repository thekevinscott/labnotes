# Python — review

## Pre-review tooling pass

Before reading a line:

```fish
uv sync
uv run pytest -x -q
uv run ruff check .
uv run ruff format --check .
uv run ty check labnotes/    # or mypy
```

If the agent didn't run these, ask. If they fail, the agent should fix before you read.

## Reading-a-PR checklist

1. **Tooling pass** — all five green?
2. **Type hints on public API** — every public function/method has explicit hints; any `Any` carries a one-line reason.
3. **Exception handling** — every `except` either re-raises, logs, or has a one-line comment explaining the conversion to data.
4. **Async correctness** — `await asyncio.sleep` and async clients inside `async def`; `gather` over bounded `Semaphore`.
5. **Docstrings** — present on public surface; *why*-oriented; signature carries the structure.
6. **Tests** — colocated `*_test.py` or in `tests/`; pytest-describe structure; fixtures over inline `with patch(...)`.
7. **`pyproject.toml` changes** — new deps reputable (see ecosystem table in [setup.md](setup.md))? In the right group (`dev` vs runtime)?
8. **Reuse over reinvention** — date parsing, retry-with-backoff, schema validation, CLI args all come from stdlib or established packages.
9. **`__init__.py`** — explicit `__all__`; heavy deps loaded through PEP 562 lazy attribute access where appropriate.
10. **Native 3.12+ syntax** — `list[T]`, `T | None`, PEP 695 generics; `from __future__ import annotations` only where the project floor demands it.
11. **Changelog fragment** — a `docs/changelog.d/` fragment added (plus `docs/migrations.d/` when breaking) for any consumer-observable change, or a `skip-changelog:` trailer present (philosophy in [../repo.md](../repo.md)).
12. **`putitoutthere.toml`** — `globs` cover every source path that should cascade.
13. **CLI shape** — a user-facing CLI is declared under `[project.scripts]` and parses its own arguments; no hand-rolled `sys.argv` handling.
14. **OS boundaries tested for real** — code that hands a path or name to the OS (sockets, files, subprocess, signals) has at least one test that runs it unmocked, at a realistic depth and length. Unit tests that stub the call only prove the code agrees with itself; a Unix socket path over 107 bytes shipped that way.
15. **Failure paths reach the user** — for each external step (config loading, subprocess, server startup), a test forces it to fail and checks the user sees a non-zero exit and the cause, not a fake success.

---

## Common type errors

- *"Incompatible types in assignment (expression has type X, variable has type Y)"* — narrowing failed; check the union members.
- *"Item 'None' of 'X | None' has no attribute 'foo'"* — narrow with `if x is None: return` or `assert x is not None`.
- *"Argument 1 to 'f' has incompatible type 'list[X]'; expected 'Sequence[X]'"* — `Sequence` is read-only; usually means `f` should take `Iterable` or `Sequence` and the caller is passing the wrong thing.
- *"Returning Any from function declared to return X"* — likely an upstream `Any` leaked in; cast at the boundary or fix the upstream.
- *"Missing return statement"* — exhaustiveness gap; some control-flow path doesn't return.
- *"Unexpected keyword argument 'foo'"* — kwargs mismatch; check `**kwargs` consumers downstream.
- *"X has no attribute '__call__'"* — you're calling something that isn't callable; structural typing failure.
