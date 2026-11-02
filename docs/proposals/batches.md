# Batches (proposal)

::: warning Proposal
Not built yet. Discussion lives in [#268](https://github.com/thekevinscott/labnotes/issues/268) and [#242](https://github.com/thekevinscott/labnotes/issues/242).
:::

## Batches

A batch is one copy of your experiment's design: its command, `[params]` and `repeats`. Each combination at each repeat is a slot in the batch. A batch is done when every slot has a run that counts.

`run` fills the slots the current batch is missing:

```sh
labnotes experiments my-experiment run
```

Run it again and it picks up whatever failed or never ran.

To run the whole design again from the top, start a new batch:

```sh
labnotes experiments my-experiment run --new
```

Name a batch to come back to it later:

```sh
labnotes experiments my-experiment run --batch sweep-2
```

Filters and `-- ARGS` apply inside the batch:

```sh
labnotes experiments my-experiment run --model=opus
```

That fills only the `opus` slots. A later plain `run` fills the rest.

Every run records its batch in `run.json`. The [TUI](../cli/tui) and [frontend](../frontend) group runs by batch and show each batch's progress.

## Failed runs

A run that fails doesn't count, so its slot stays open and the next `run` plans it again. The new try starts from scratch in a new folder.

## Resuming

A long run that dies partway loses its work if it starts from scratch. If your experiment can pick up where it left off, say so in `experiment.toml`:

```toml
resumable = true
```

Labnotes can't know whether your code can resume, so this is off unless you set it.

In a resumable experiment, a slot keeps one run folder for every try. Each try is an attempt. The next `run` adds an attempt to the failed run, so `{run_dir}` already holds what the last attempt wrote. Your code reads it and continues.

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox/
            run.json
            checkpoint.json
            attempts
                20261020-000429/
                    stdout.txt
                    stderr.txt
                20261021-093112/
                    stdout.txt
                    stderr.txt
</Tree>

`run.json` lists the attempts, each with its start, end, exit code, how it ended, and the git commit it ran. The run counts when its last attempt counts.

To start a failed run from scratch for one launch, pass `--fresh`:

```sh
labnotes experiments my-experiment run --fresh
```

A run that exits 75 is [retried](../api/config#retries-1) the same way: in a resumable experiment the retry is a new attempt in the same folder.

## Crashed runs

While an attempt runs, labnotes holds a lock on its run folder and releases it when the attempt ends. A second attempt can't start on a locked folder.

If the machine reboots or the process is killed, `run.json` may still say the run is running. Nothing holds its lock, so labnotes knows it died and treats it as failed.

## Code changes

Each attempt runs your current code and records its git commit. If you fix a bug and resume, the new attempt runs the fix. Labnotes warns when attempts of one run used different commits, and never throws away finished runs because the code changed.

## Open questions

- What the default batch is called, and whether `run` refuses to continue a batch whose `[params]` or `command` changed.
- Whether run folders are flat with the batch recorded in `run.json`, or nested under a folder per batch.
- Whether `counts` and [views](../api/views) query runs or attempts.
- Whether the lock is reliable on network filesystems.
