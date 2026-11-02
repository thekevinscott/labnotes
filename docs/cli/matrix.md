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

To run part of the matrix, name params on the command line:

```sh
labnotes experiments my-experiment run --model=opus --effort=low
```

That plans only the combinations where `model` is `opus` and `effort` is `low`. Each flag must name a param in `[params]` and one of its values; anything else is an error.

Repeat a param to run several of its values in one launch:

```sh
labnotes experiments my-experiment run --effort=high --model=opus --model=haiku
```

That plans the combinations where `effort` is `high` and `model` is `opus` or `haiku`. Values are taken whole, so a value with a comma in it is still one value. The rest of the matrix still counts toward progress, so a plain `run` later picks up the combinations this one skipped.

A run that exits 75 is [retried](../api/config#retries-1) in the same `run`. The failed run doesn't count, so its retry takes its place and the combination still gets `repeats` runs, not more.

## Failed runs

By default a failed run stays as it is, and the next `run` gives its combination a new folder. Set `continues = true` to invoke the failed run again in its own folder instead:

```toml
mode = "matrix"
continues = true
```

The next `run` takes each failed run in a combination that is short of `repeats` and invokes it again, with the same params and the same `{run_dir}`. A run that fails, is stopped, or was lost when labnotes died all count as failed. Excluded runs and runs that count are left alone and get new folders. A run that exits 75 retries in its folder too.

The folder then holds every invocation. `run.json` lists them under `"invocations"`, each with its own times, exit code, commit, and args, and each writes its own `stdout-<time>.txt` and `stderr-<time>.txt`. See [`continues`](../api/config#continues) for the fields.

Your command finds what its last invocation left in `{run_dir}` and decides what to do with it. labnotes does nothing to those files. In return, your command must never delete `run.json`, `stdout-*`, `stderr-*`, or `run.lock`. labnotes holds a lock on `run.lock` while an invocation runs, and a second `run` skips any run that is locked.

Runs will appear on disk as flat folders, each named for the UTC time it was planned:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox/
        20261020-000431-quiet-river/
</Tree>

You can use the [TUI](tui) to prioritize and manage which runs are in flight, and concurrency. The [frontend](../frontend) shows progress toward `repeats` for each combination.
