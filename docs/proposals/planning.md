# Planning and runs (proposal)

::: warning Proposal
Not built yet. Discussion lives in [#268](https://github.com/thekevinscott/labnotes/issues/268) and [#242](https://github.com/thekevinscott/labnotes/issues/242).
:::

## The idea

An experiment in labnotes is a command you want to run many times with different settings. You describe it in `experiment.toml`:

```toml
command = "uv run python run.py --output {run_dir}"
repeats = 3

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

This asks for every combination of `model` and `effort`, three times each: twelve runs. Each run gets its own folder under `runs/`, where your command writes its results and labnotes keeps a `run.json` saying how it went.

You start runs with one command:

```sh
labnotes experiments my-experiment run
```

`run` looks at the folders already on disk, works out which of the twelve runs are still missing, and starts those. A run is missing if it never ran, or if it ran and failed. Run it again later and it starts whatever is still missing. When nothing is missing, it says so and does nothing.

That is the whole model. The rest of this page is what happens in the situations that come up in practice.

## You only want some of it

Name the settings you want on the command line:

```sh
labnotes experiments my-experiment run --model=opus
```

This starts only the missing `opus` runs. A later plain `run` starts the rest.

## You want a fresh set of results

By default every successful run on disk counts, so each `run` builds on the last. Sometimes you want to start over: you changed your prompt and want twelve new runs, not to top up the old ones. Start a new launch:

```sh
labnotes experiments my-experiment run --new
```

A launch is one `run` command, and every run records the launch that started it. A new launch counts only its own runs, so it starts all twelve again. Your old runs stay on disk untouched.

If your newest `--new` launch still has runs missing, a plain `run` continues it. Once it is complete, a plain `run` goes back to counting every run. To continue an older launch, name it:

```sh
labnotes experiments my-experiment run --launch 20261102-brave-fox
```

## Your machine reboots partway through

Before `run` starts anything, it creates a folder for every run it intends to start, marked `planned`. Then it starts them.

If the machine goes down, those folders are still there. The runs that were going are marked `running`, but no process is behind them any more. Labnotes notices this the next time you use it, because a live run holds a lock on its folder and a dead one can't. It marks those runs `killed`.

Run `run` again and it starts everything that was planned but never started, and everything that was killed.

## A long run fails and you don't want to lose its work

When `run` starts a failed run again, it uses the same run folder. Each try is an attempt.

Every attempt starts with an empty `{run_dir}`. Before a new attempt starts, labnotes moves what the last one wrote into `attempts/`, next to its logs:

<Tree>
my-experiment
    runs
        20261102-000429-brave-fox/
            run.json
            results.json
            attempts
                20261102-000429/
                    checkpoint.json
                    stdout.txt
                    stderr.txt
                20261103-093112/
                    stdout.txt
                    stderr.txt
</Tree>

Here the first attempt died after saving `checkpoint.json`. The second attempt started clean, found the checkpoint through `{last_attempt_dir}`, picked up from it, and wrote `results.json`.

If your code can resume, it reads `{last_attempt_dir}` and continues. If it can't, it ignores it and starts over, and nothing left behind gets in its way. Labnotes doesn't decide which, because only your code knows whether its saved state is still good.

`run.json` lists every attempt: when it started and ended, its exit code, whether it failed, was stopped or was killed, the git commit, and any `-- ARGS`. The run's own exit code and status are its last attempt's.

If several runs of one combination failed, each gets its own next attempt. A run that fails again gets another attempt the next time.

## A run hits a temporary error

A run that exits 75 is [retried](../api/config#retries-1) within the same `run`, as a new attempt in the same folder.

## A run doesn't count, but didn't fail

Some runs succeeded but don't count: you excluded them by hand, or your [`counts`](../api/config) rule leaves them out, like `created > '2026-10-01'`. Labnotes never starts another attempt on those. If their combination is still short, it gets a new run in a new folder.

## You run two launches at once

Planning happens under a lock on the experiment. While one `run` is deciding what to start and creating its folders, another waits. The second one sees the first one's planned folders and doesn't start the same runs. You get twelve runs, not more.

## You change your code halfway through

Every attempt records the git commit it ran. If the runs for one combination came from different commits, labnotes warns you in the TUI and frontend.

`-- ARGS` are recorded too, but don't trigger the warning: passing different arguments is something you do on purpose.

Labnotes never throws runs away because something changed. If the old runs shouldn't count, exclude them or start a new launch.

## You stop a run

Stopping a run from the TUI, pressing Ctrl-C, or closing the terminal marks the attempt `stopped`. A stopped run never counts as a success, so the next `run` picks it up again.

## Setup and teardown hooks

Hooks run once per `run` command: `setup` before the first run starts, `teardown` after the last one ends. State set with `set_state` lasts for that command only. Continuing a launch later runs `setup` again from scratch.

## Open questions

- Whether the locks hold on network filesystems.
- How runs from before this design map in.
