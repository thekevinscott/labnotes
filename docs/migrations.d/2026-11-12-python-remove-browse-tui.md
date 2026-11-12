## Summary

The browse TUI (experiments list, experiment screen, run screen) is removed. It opened its own repo-wide file watcher, which could exhaust inotify. The run TUI, which gets its data from the daemon, is the TUI that stays. The bare listing commands go with it.

## Required changes

Before: `labnotes experiments` listed experiments, and `labnotes experiments NAME` showed one experiment. In a terminal both opened the browse TUI; piped or with `--format`, both printed rows.

After: name an experiment and an action. List runs with `labnotes experiments NAME runs [--format json]`. Watch or control a run with `labnotes experiments NAME run` or `attach`. Notes, configs and run pages are in the web app (`labnotes server`).

## Deprecations removed

`labnotes experiments` and `labnotes experiments NAME` with no action, with or without `--format`. Custom `[views]` now appear only in the run TUI.

## Behavior changes without code changes

`labnotes experiments` and `labnotes experiments NAME` exit 2 with `Give an experiment and an action: runs, run, attach or stop.`, in a terminal or piped. Scripts that parsed their output, including the `daemon` and `running_cells` columns, get nothing on stdout.

## Verification

Run `labnotes experiments`; it exits 2 and names the actions. Run `labnotes experiments NAME runs`; it prints the runs table and exits 0.
