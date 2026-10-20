# Adhoc

`adhoc` is the default mode. To set a mode, use `mode` in `experiment.toml`, or under `[experiments]` in `.labnotes.toml` for every experiment. The experiment's own setting wins.

Every `run` plans each combination of `[params]`, `repeats` times, no matter what's already on disk. Use it when each run of the experiment is its own attempt, like trying a change and looking at the result.

Each `run` command gets one folder, named for the UTC time it was planned (`runs/20261020-000429-brave-fox`), and its runs nest inside it. Nested folders are named from the params that vary, or a haiku name when nothing varies. An interrupted `run` doesn't resume; the next one starts a new set.

The frontend groups an `adhoc` experiment's runs by the `run` that made them. When a `run` plans a single run, the CLI opens straight on its output.
