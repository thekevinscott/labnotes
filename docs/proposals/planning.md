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

## Your machine reboots partway through

Before `run` starts anything, it creates a folder for every run it intends to start, marked `planned`. Then it starts them.

If the machine goes down, those folders are still there. The runs that were going are marked `running`, but no process is behind them any more. Labnotes notices this the next time you use it, because a live run holds a lock on its folder and a dead one can't. It marks those runs `killed`.

Run `run` again and it starts everything that was planned but never started, and everything that was killed. If the launch you were in was a `--new` one, continue it by name:

```sh
labnotes experiments my-experiment run --launch 20261102-brave-fox
```

## A long run fails and you don't want to lose its work

When `run` starts a failed run again, it reuses the same folder. Each try is an attempt, and the folder keeps every attempt:

<Tree>
my-experiment
    runs
        20261102-000429-brave-fox/
            run.json
            checkpoint.json
            attempts
                20261102-000429/
                    stdout.txt
                    stderr.txt
                20261103-093112/
                    stdout.txt
                    stderr.txt
</Tree>

Whatever your code saved last time, like `checkpoint.json` above, is still in `{run_dir}`. `run.json` lists each attempt: when it started and ended, its exit code, whether it failed, was stopped or was killed, and which git commit it ran.

Your code decides what to do with that. If its saved state is still good, it continues from there. If not, it clears the folder and starts over. Labnotes doesn't make this call, because only your code knows whether its saved state is still valid.

To make every failed run start clean for one launch, pass `--fresh`:

```sh
labnotes experiments my-experiment run --fresh
```

## You run two launches at once

Planning happens under a lock on the experiment. While one `run` is deciding what to start and creating its folders, another waits. The second one sees the first one's planned folders and doesn't start the same runs. You get twelve runs, not more.

## You change your code halfway through

Every attempt records the git commit and the exact command it ran. If the runs for one combination came from different commits, labnotes warns you in the TUI and frontend.

It never throws runs away because something changed. If the old runs shouldn't count, exclude them or start a new launch.

## You stop a run

Stopping a run from the TUI, pressing Ctrl-C, or closing the terminal marks the attempt `stopped`. A stopped run never counts as a success, so the next `run` picks it up again.

## Open questions

- Whether the locks hold on network filesystems.
- How runs from before this design map in.
