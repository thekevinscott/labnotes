## Summary

The `adhoc` / `matrix` split is gone, and `continues` is now required. Every experiment plans the way `matrix` did: `run` plans the combinations of `[params]` that have fewer than `repeats` runs that count, so running again picks up whatever failed or never ran, and plans nothing once every combination is done. Runs are written to flat folders under `runs/`; a `run` that plans several runs no longer makes a shared invocation folder. Every experiment says whether a failed run continues in its own folder or starts over in a new one, because both choices cost hours when they are wrong.

## Required changes

| Before | After |
| --- | --- |
| `mode = "adhoc"` or `mode = "matrix"` in `experiment.toml` | Delete the line. |
| `mode = ...` under `[experiments]` or `[experiment]` in `.labnotes.toml` | Delete the line. |
| No `continues` in `experiment.toml` | `continues = false` to keep starting failed runs over in new folders, or `continues = true` to invoke them again in their own folders. |
| `continues = true` next to `mode = "matrix"` | `continues = true` alone. |

`continues` can also go under `[experiment]` in `.labnotes.toml`, which every `experiment.toml` builds on.

To repeat a finished ad hoc experiment from scratch, make a new experiment with `labnotes experiments new NAME --from OLD`. The copy drops `mode` and gets `continues = false` if it had none.

## Deprecations removed

`mode` was removed without a deprecation period. Setting it anywhere is a config error.

## Behavior changes without code changes

- An experiment that relied on the old default (`adhoc`) used to run the full grid on every `run`. It now runs only what is missing. A second `run` of a finished experiment plans nothing and prints `Nothing to run: every combination has its repeats.`
- Runs that an ad hoc `run` would have nested in an invocation folder (`runs/<stamp>/<param-name>/`) are now flat, stamped folders (`runs/20261020-000429-brave-fox/`). Old nested runs stay where they are; `experiments NAME runs`, the TUI and the frontend still list them, grouped by their invocation folder, and they count toward `repeats`.
- `{invocation_dir}` in `command` and `[env]` is now always the run's own folder, the same as `{run_dir}`.
- The hook state file (`LABNOTES_STATE`, `LABNOTES_RUN_STATE`) is always a temporary file, removed after teardown. It used to be `state.json` in the invocation folder or the lone run's folder.
- The TUI still opens straight on the output of a `run` that plans one run.
- A second `run` of an experiment that is already running refuses before any run starts: `NAME is already running in another labnotes run.` That includes a filtered `run --model=x` next to another `run` of the same experiment. Different experiments still run side by side.
- `experiments --json` no longer has a `mode` key on each experiment.
- The frontend's experiment page no longer shows a mode chip, and every experiment gets the grid view.

## Verification

```
labnotes experiments NAME run
```

With `mode` still set, it exits non-zero before any run starts, with an error that starts `mode was removed`. Without `continues`, it exits non-zero with an error that asks for `continues = true or continues = false`. With both fixed, a finished experiment prints `Nothing to run: every combination has its repeats.` and `0 passed, 0 failed.`
