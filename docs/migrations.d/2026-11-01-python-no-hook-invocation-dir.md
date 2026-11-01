## Summary

`setup`, `teardown`, and `meta` no longer get `{invocation_dir}`. Hooks share values through `set_state()` and `get_state()`, so they don't need a folder placeholder. `{run_dir}` was already unavailable there. Run commands keep both placeholders.

## Required changes

Remove `{invocation_dir}` from `setup`, `teardown`, and `meta` in `.labnotes.toml`, `experiment.toml`, and `--setup` / `--teardown` flags. Where setup wrote a file into the folder for teardown or runs to read, save the value with `set_state()` instead:

Before:

```toml
setup = "start-box > {invocation_dir}/box.txt"
teardown = "stop-box $(cat {invocation_dir}/box.txt)"
```

After:

```python
# setup.py
from labnotes import set_state
set_state({"box": start_box()})

# teardown.py
from labnotes import get_state
stop_box(get_state()["box"])
```

```toml
setup = "python setup.py"
teardown = "python teardown.py"
```

A hook that needs a value from `[env]` must not read one that uses `{invocation_dir}`; that variable is no longer in the hook's environment.

## Deprecations removed

`{invocation_dir}` in hooks was removed without a deprecation period.

## Behavior changes without code changes

An `[env]` value that uses `{invocation_dir}` is left out of the `setup`, `teardown`, and `meta` environment. In matrix mode with several planned runs this used to fail the invocation; now the runs get it, each set to its own `{run_dir}`. The hook state file (`LABNOTES_STATE`, `LABNOTES_RUN_STATE`) stays where it was.

## Verification

Run `labnotes experiments NAME run` with `setup = "echo {invocation_dir}"`. It should exit non-zero before setup runs with `setup command echo {invocation_dir} uses {invocation_dir}; setup, teardown, and meta get no folder placeholders. Share values with set_state() and get_state().` With the placeholder removed, the run should start.
