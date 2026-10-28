## Summary

Run commands and hooks now use the actual run and invocation folders, so their placeholders refer to paths that exist. `{run_id}` and `{invocation_id}`, shipped in v0.0.128, are removed.

## Required changes

Replace `{run_id}` with `{run_dir}` and `{invocation_id}` with `{invocation_dir}` in `command` and `[env]` values in `.labnotes.toml` and `experiment.toml`. In `setup`, `teardown`, and `meta`, replace either old ID placeholder with `{invocation_dir}`; `{run_dir}` is never filled there. These are absolute paths, so remove any code that prepended the runs folder to an ID. Shell commands receive shell-quoted paths; `[env]` values receive raw paths.

In matrix mode, `{invocation_dir}` in a hook requires exactly one planned run. In multi-run adhoc mode, it names the shared group folder. The folder exists before setup starts, so setup can write files there for teardown to read.

## Deprecations removed

`{run_id}` and `{invocation_id}` were removed without a deprecation period.

## Behavior changes without code changes

For a single adhoc run or any matrix run, `{invocation_dir}` equals that attempt's `{run_dir}`. For multi-run adhoc commands, all runs and hooks share the group folder as `{invocation_dir}`. Hooks for a retried single run use the first planned run's folder.

## Verification

Run `labnotes experiments NAME run` with `command` set to `printf '%s\n' {run_dir} {invocation_dir}`. Its `stdout.log` should contain two absolute paths; they match for a single adhoc run or a matrix run. With several adhoc runs, the second path is their common parent folder. Set `setup` to `test -d {invocation_dir}` to confirm the folder exists before setup. A hook using `{run_dir}` should fail before setup or any run starts with an error directing you to `{invocation_dir}`.
