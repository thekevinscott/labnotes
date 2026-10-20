# Modes

An experiment runs in one of two modes, `adhoc` or `fill`. Set `mode` in `experiment.toml`, or under `[experiments]` in `.labnotes.toml` for every experiment. The experiment's own setting wins. Without either, it's `adhoc`.

## adhoc

Every `run` plans the full grid: each combination of `[params]`, `repeats` times, no matter what's already on disk. Use it when each run of the experiment is its own attempt, like trying a change and looking at the result.

Each `run` command gets one folder, named for the UTC time it was planned (`runs/20261020-000429-brave-fox`), and its runs nest inside it. Nested folders are named from the params that vary, or a haiku name when nothing varies. An interrupted `run` doesn't resume; the next one starts a new set.

The frontend groups an `adhoc` experiment's runs by the `run` that made them. When a `run` plans a single run, the CLI opens straight on its output.

## fill

A combination of `[params]` is full once it has `repeats` runs that count. `run` plans only what's missing, so running again fills in what failed or never ran. Use it when you want a fixed number of good runs per combination and don't care how many tries it takes.

By default a run counts when it exited 0 and its `run.json` doesn't hold `"excluded": true`. `counts` in `experiment.toml` replaces that rule with a SQL condition over `runs`, for example `exit_code = 0 AND created > '2026-10-01'`.

Run folders are flat, each named for the UTC time it was planned. The frontend shows progress toward `repeats` for each combination.
