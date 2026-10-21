# Matrix

`matrix` mode lets you define a list of experiments you desire to run, and lets you iteratively work towards running all of them. It's well suited for long running, expensive, or sprawling experiments.

You can define `matrix` mode by setting `mode = "matrix"` in your config:

```toml
command = "uv run python run.py --output {run_dir}"
repeats = 5
mode = "matrix"

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

Each combination of `[params]` is done once it has `repeats` runs that count. `run` plans only what's missing, so running again picks up whatever failed or never ran.

By default a run counts when it exited 0 and its `run.json` doesn't hold `"excluded": true`. Set `counts` in `experiment.toml` to replace that rule with a SQL condition over `runs`, like `exit_code = 0 AND created > '2026-10-01'`.

Runs will appear on disk as flat folders, each named for the UTC time it was planned:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox/
        20261020-000431-quiet-river/
</Tree>

You can use the [TUI](tui) to prioritize and manage which runs are in flight, and concurrency. The [frontend](../frontend) shows progress toward `repeats` for each combination.
