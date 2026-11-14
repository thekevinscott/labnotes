## Summary

`labnotes experiments NAME runs` is removed. It was a second read path next to the run TUI, and the daemon's API (#454) will be the way to read runs from a script.

## Required changes

Before: `labnotes experiments NAME runs [--format table|json]` listed the experiment's runs with `counted`, `memory` and `size`.

After: watch runs in the run TUI with `labnotes experiments NAME run`, or reopen it on whatever is running with `labnotes experiments NAME attach`. The TUI shows each run's status, memory and size. Until the daemon API (#454) lands, scripts read each run folder's `run.json`.

## Deprecations removed

The `runs` action and the `--format` option of `labnotes experiments`.

## Behavior changes without code changes

`labnotes experiments NAME runs` exits 2 with `Unknown action runs. Use run, attach or stop.` With no action, the usage error names `run, attach or stop`. `--format` is no longer an option, so passing it is a usage error.

## Verification

Run `labnotes experiments NAME runs`; it exits 2 with `Unknown action runs. Use run, attach or stop.`
