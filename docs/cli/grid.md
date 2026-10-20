# Grid

Set `mode = "fill"` to run in grid mode.

A combination of `[params]` is full once it has `repeats` runs that count. `run` plans only what's missing, so running again fills in what failed or never ran. Use it when you want a fixed number of good runs per combination and don't care how many tries it takes.

By default a run counts when it exited 0 and its `run.json` doesn't hold `"excluded": true`. `counts` in `experiment.toml` replaces that rule with a SQL condition over `runs`, for example `exit_code = 0 AND created > '2026-10-01'`.

Run folders are flat, each named for the UTC time it was planned. The frontend shows progress toward `repeats` for each combination.
