## Summary

Experiment runs always use the TUI and its daemon. This removes the foreground runner, which could plan duplicate repeats when two clients overlapped.

## Required changes

Before: `labnotes experiments NAME run --headless` or `labnotes experiments NAME run` with redirected output.

After: run `labnotes experiments NAME run` in a terminal or PTY. Scripts that need results can read `labnotes experiments NAME runs --format json` after the TUI reports completion.

## Deprecations removed

`--headless` was removed.

## Behavior changes without code changes

`run` without a terminal exits 2 with a usage error. The daemon survives a lost TUI. Two invocations through one daemon share the repeat budget.

## Verification

Run `labnotes experiments NAME run` in a terminal; the live table opens. Run the same command with stdout redirected; it exits 2 and says `run requires a terminal.`
