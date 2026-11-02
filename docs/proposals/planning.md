# Planning and runs (proposal)

::: warning Proposal
Not built yet. Discussion lives in [#268](https://github.com/thekevinscott/labnotes/issues/268) and [#242](https://github.com/thekevinscott/labnotes/issues/242).
:::

## Planning

`run` launches what your experiment is missing. The design in `experiment.toml` asks for `repeats` runs of every combination of `[params]`. `run` takes that, subtracts the runs on disk that already count, and launches the difference:

```sh
labnotes experiments my-experiment run
```

Run it again and it picks up whatever failed or never ran. If nothing is missing, it plans nothing.

Filters narrow the design for one launch:

```sh
labnotes experiments my-experiment run --model=opus
```

## Launches

Every `run` is a launch, and every run records the launch that planned it.

By default every run that counts is in scope, so launches build on each other. To make a fresh pass that ignores earlier runs, start a new launch:

```sh
labnotes experiments my-experiment run --new
```

Only that launch's runs count toward it. If it crashes partway, continue it:

```sh
labnotes experiments my-experiment run --launch 20261102-brave-fox
```

Hooks, `state.json` and the TUI work per launch.

## Plan first, then start

`run` writes a folder for every run it plans before it starts any of them, with status `planned`. It does this while holding a lock on the experiment, so two launches never plan the same missing run.

A launch that dies leaves its unstarted runs on disk. The next `run` sees them and starts them.

## Runs and attempts

A run folder holds every try at that run. Each try is an attempt.

<Tree>
my-experiment
    runs
        20261102-000429-brave-fox/
            run.json
            attempts
                20261102-000429/
                    stdout.txt
                    stderr.txt
                20261103-093112/
                    stdout.txt
                    stderr.txt
</Tree>

`run.json` lists the attempts, each with its start, end, exit code, how it ended, the git commit, and the command as launched. The run's own `exit_code` and status are its last attempt's, so [`counts`](../api/config) and [views](../api/views) read runs the same way however many attempts they took.

## Failed runs

A failed run doesn't count, so the next `run` plans it again as a new attempt in the same folder. `{run_dir}` still holds what earlier attempts wrote, and `run.json` says how each one ended.

Your code decides whether to pick up from that state or clear it and start over. Labnotes can't know whether saved state is still valid; your code can.

To force a clean start, pass `--fresh`. Failed runs keep their folders and new runs take their place:

```sh
labnotes experiments my-experiment run --fresh
```

## Live and dead runs

While an attempt runs, its process holds a lock on the run folder. The lock goes away when the process ends, however it ends.

A run whose `run.json` says running but whose lock nobody holds is dead. Labnotes marks it killed the next time it looks, and plans it again.

Stopping from the TUI, Ctrl-C or a closed terminal records the attempt as stopped, never as a success.

## Changes between runs

Each attempt records the commit and command it ran. Labnotes warns when the runs counting toward one combination, or the attempts of one run, used different ones. It never discards runs because something changed; exclude them, or start a new launch.

## Open questions

- Whether the locks hold on network filesystems.
- How existing runs map in: matrix runs into one launch, each adhoc group folder into a launch of its own.
