# Adhoc

`adhoc` lets you run one-off experiments. `adhoc` is the default mode.

Every `run` plans each combination of `[params]`, `repeats` times, no matter what's already on disk. Use it when each run is its own attempt, like trying a change and looking at the result. An interrupted `run` doesn't resume; the next one starts a new set.

A `run` that plans a single run writes one folder, named for the UTC time it was planned:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox/
</Tree>

When multiple parameters or `repeats` give a `run` more than one run, it gets an invocation folder with that name, and its runs nest inside it, each named from the params that vary:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox
            opus-low-1a2b/
            opus-high-3c4d/
            sonnet-low-5e6f/
            sonnet-high-7a8b/
</Tree>

When nothing varies but `repeats` is more than 1, the nested runs get haiku names instead, like `quiet-river`.

`run --model=opus` plans only the combinations where `model` is `opus`, the same way as in [matrix](matrix) mode.

A run that exits 75 is [retried](../api/config#retries-1) in a new run folder: inside the same invocation folder when there is one, or a new stamped folder for a lone run.

`{invocation_dir}` in `command`, `setup` or `teardown` becomes the invocation folder's absolute path when several runs are planned. That folder exists before setup runs, so setup can leave files there for teardown. `{run_dir}` in `command` is each run folder's absolute path. For a single planned run, `{invocation_dir}` is its first attempt's folder and stays there if the run retries; `{run_dir}` moves to each retry's folder. Both are shell-quoted. `{run_dir}` is unavailable in setup and teardown. See [`command`](../api/config#command).

The frontend groups an `adhoc` experiment's runs by the invocation that made them. When an invocation plans a single run, the CLI opens straight on its output.
