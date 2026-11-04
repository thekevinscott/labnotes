# Working with Experiments

`labnotes` offers a CLI for managing and running experiments. Ensure that you've [first created a configuration file](../getting-started).

## Viewing Experiments

![Browsing experiments: an experiment and a run's output](/demos/experiments.gif)

View experiments with:

```bash
uvx labnotes experiments
```

In a terminal, this opens a [browser](tui#browsing) that lists each experiment's name, last run, created, files (num) and runs (num). Open an experiment to see its runs, and open a run to read its output. The browser updates as runs start and finish.

Start on a particular experiment with:

```bash
uvx labnotes experiments foo
```

Pass `--format table` or `--format json` to print instead. `foo runs` prints the experiment's runs:

```bash
uvx labnotes experiments foo runs --format table
```

Piped output and scripts always get a table, but agents may run under a terminal, so they should always pass `--format`.

The list marks an experiment with a live daemon and shows its number of running cells. `--format json` exposes these as `daemon` and `running_cells`.

## Creating Experiments

Create an experiment from the command line:

```bash
uvx labnotes experiments new sanity-3 \
  --command "uv run python run.py --out {run_dir}" \
  --param model=opus --param model=sonnet \
  --repeats 3
```

This makes the `sanity-3` folder and writes its `experiment.toml`. Only the name is required; anything you leave out keeps the starter's value. The command line never holds config of its own: everything ends up in the file, where you can read and diff it. Hooks, `[env]` and `counts` are set by editing the file.

To start from another experiment, pass `--from`:

```bash
uvx labnotes experiments new sanity-4 --from sanity-3 --param model=haiku
```

This copies `sanity-3`'s `experiment.toml` and files, never its runs, and records `from = "sanity-3"`. Flags given with it replace the copied values; `--param model=...` replaces only `model`'s values. `new` refuses a folder that already exists. labnotes works on the folder on disk and makes no assumption about how you keep it (git, DVC, Hugging Face). See the [CLI reference](../api/cli#experiments) for every flag.

## Running Experiments

You can run an experiment with:

```bash
uvx labnotes experiments foo run
```

In a terminal, this starts or reuses a daemon for the experiment and opens the [TUI](tui). The daemon owns the cells. The TUI reads their state from disk and sends control commands over a local socket. Closing the terminal or losing an SSH connection leaves the runs going; run the command again to open a new TUI. Each experiment has its own daemon for each labnotes version, and it exits shortly after its last run finishes and its last TUI closes.

Use `--headless` to keep the run in the foreground and print events without opening the TUI. In this mode, Ctrl-C or SIGHUP asks labnotes to stop its cells cleanly, including when a terminal or SSH connection closes.

To stop every cell owned by a live experiment daemon from another shell, run:

```bash
labnotes experiments foo stop
```

The command reports an error and exits non-zero when no daemon is live.

To run an experiment needs a script and parameters defined. This should be defined in an `experiment.toml` file in the experiment folder; it can also be provided on the command line (`uvx labnotes experiments foo run --experiment-config ./foo.toml`).

The TOML file defines the dynamic parameters along with the script to run:

```toml
command = "uv run python run.py --output {run_dir}"
repeats = 5
continues = false

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

The script can be any command. Each combination of parameters runs `repeats` times; see [Planning Runs](#planning-runs) for how `run` works toward that. `continues` is required; see [Failed runs](#failed-runs). Dynamic parameters will be passed as arguments to the script (`--model opus --effort low`). In a Git project, labnotes copies tracked and untracked, non-ignored files into a fresh `labnotes-` folder in the system temporary directory when the invocation starts. Setup, meta, every run, and teardown use that snapshot as their working directory, so later edits to the project do not change code seen by the invocation. Uncommitted changes are included. Ignored paths such as `data/` and `.env` are linked to the project; reads and writes through them remain live. The snapshot is removed when the invocation ends. Outside a Git repository, labnotes warns and runs from the live project directory.

Labnotes does not build an environment in the snapshot. If your command needs one derived from the source, create it in `setup` (for example, `setup = "uv sync"`), before concurrent runs start. Ignored virtual environments are excluded so `uv sync` or `uv run` can create an isolated environment in the snapshot. The snapshot includes Git metadata at the invocation commit, including tags and the copied working-tree changes.

Each run gets its own run folder in the project; `{run_dir}` in the command becomes that folder's absolute path, so the script knows where to write its output. `LABNOTES_RUN` is also an absolute project path. `{invocation_dir}` is the same folder as `{run_dir}`. Both placeholders are shell-quoted.

Dynamic parameters get recorded for a particular run in a run.json file in the run folder, along with when it started, when it ended, and its exit code. `command` in run.json holds the exact shell command the run executed, with `{run_dir}`, `{invocation_dir}` and the params filled in. It is written before the run starts, so a run that was killed still has it, and editing `experiment.toml` later doesn't hide what an earlier run did. The script's stdout and stderr are saved alongside. For output too noisy to read raw, such as a model's thinking, the script can write structured blocks with [`log`](../api/sdk#log); they go to `log.jsonl` in the same folder. While the run goes, labnotes samples its memory every 5 seconds into `memory.jsonl`, one JSON line per sample; see [`memory_interval`](../api/config#memory-interval).

Each run folder also contains `git-sha.txt` with the commit SHA and `git-diff.patch` with every change the snapshot ran with, taken at the start of the invocation: `git diff HEAD` for tracked files, then each untracked, non-ignored file as a new file. Untracked files that are binary or larger than 1 MiB appear by name only, as `Binary files ... differ`. Its `run.json` records `git`: `{"commit": "<full HEAD SHA>", "dirty": false}` from the same moment. `dirty` is true when that patch is not empty, so an untracked file counts. Ignored files don't. Add your run folders to `.gitignore`, or each run's output counts toward the next run's `dirty` and patch. `git` is `null` outside a Git repository or in one without a commit; a repository without a commit also runs from the live tree. Older records lack this key.

labnotes sets `LABNOTES_RUN` to the absolute run folder path in each script's environment, unique across experiments and projects on the machine. If the script starts a Docker container, label it with `docker run --label "labnotes.run=$LABNOTES_RUN" ...` so labnotes includes that container's active memory in the run's samples. labnotes does not modify the script's Docker commands. Containers without the label are not counted.

For botbox sandboxes, labnotes sets `BOTBOX_LABELS` with `labnotes.run=<absolute run folder>`, so their memory is counted with no configuration. Existing labels from the caller's environment or `[env]` are preserved, with the labnotes label appended on a new line (one `key=value` per line). Consumers should not set the `labnotes.run` label themselves in `BOTBOX_LABELS` or experiment configuration. Only runs receive the generated label; setup, teardown, and meta hooks do not. Retries receive their new attempt's folder, matching `LABNOTES_RUN`.

Running an experiment opens a TUI that shows a table of all runs. Pending runs are slightly grayed. Runs default to 1 at a time but concurrency can be added with a `--concurrency` flag. The TUI lets you filter runs by a parameter, raise or lower concurrency as runs go, and kill specific runs. Failed runs show in red.

A script that exits 75 (`EX_TEMPFAIL`) is saying it couldn't run for a reason outside the experiment, like no capacity. labnotes retries those on its own with the same params: after 30 seconds, then 60, up to `retries` times (3 by default). Each retry gets its own run folder, linked back by `retry_of` in its `run.json`. Every other non-zero exit is left alone. The failed run doesn't count, so its retry takes its place and the combination still gets `repeats` runs, not more. See [`retries`](../api/config#retries-1).

Two `run` invocations of the same experiment can run at once. In a terminal they share the experiment's daemon, while each TUI follows its own invocation. Run locks prevent both invocations from claiming the same cell.

Ctrl-C opens a quit prompt while runs are going. Press `s` to stop them, Enter or `l` to leave them running, or Escape to return to the TUI. The `x` key stops the selected run, and `+` or `-` changes concurrency through the daemon.

`--timeout 1800` stops any run still going after 1800 seconds (30 minutes), with SIGTERM and then SIGKILL 5 seconds later. Each run gets its own 30 minutes. Its `run.json` records `"error": "timed out after 30m 00s"`, so a timeout reads differently from a crash.

`run.json` also records why a run ended, in `ended_by`: `"timeout"` for `--timeout`, `"stop"` when labnotes stopped it (Ctrl-C, SIGHUP, or killing the run in the TUI), `"signal"` when a signal labnotes didn't send ended it, like the kernel's out-of-memory killer, `"lost"` when the process running it died without labnotes noticing (labnotes was killed, the machine rebooted), and `null` when the script exited on its own. `signal` holds the signal number, read from the exit code: a negative code, or 128 plus the number when the shell reports it (137 is SIGKILL, 9). A script that catches a signal and exits with its own code leaves `signal` null, and one that exits 137 on purpose reads as SIGKILL.

`run.json` also records the labnotes version that ran the run, in `labnotes_version`, and the labnotes command line that started it, in `labnotes_command`, so you can tell which release ran an old run and launch it again the same way.

The next `run` invocation marks lost runs when it starts: an unfinished run whose `pid` is gone, or now belongs to another process, gets `"ended_by": "lost"` and the time it was noticed as `ended`. Its `exit_code` stays `null`, since nobody saw it exit. A run whose process is still alive stays unfinished until a later run start finds it gone.

## Planning Runs

An experiment is a list of runs you want: every combination of `[params]`, `repeats` times. `run` works toward that list. Each combination is done once it has `repeats` runs that count, and `run` plans only what's missing, so running again picks up whatever failed or never ran. When nothing is missing, `run` says so and plans nothing.

By default a run counts when it exited 0 and its `run.json` doesn't hold `"excluded": true`. Set `counts` in `experiment.toml` to replace that rule with a SQL condition over `runs`, like `exit_code = 0 AND created > '2026-10-01'`.

To start over with the same design, copy it with `labnotes experiments new NAME --from OLD`. An experiment holds one design and the runs toward it.

### Running part of the grid

To run some of the combinations, name params on the command line:

```sh
labnotes experiments my-experiment run --model=opus --effort=low
```

That plans only the combinations where `model` is `opus` and `effort` is `low`. Each flag must name a param in `[params]` and one of its values; anything else is an error.

Repeat a param to run several of its values in one launch:

```sh
labnotes experiments my-experiment run --effort=high --model=opus --model=haiku
```

That plans the combinations where `effort` is `high` and `model` is `opus` or `haiku`. Values are taken whole, so a value with a comma in it is still one value. The rest of the grid still counts toward progress, so a plain `run` later picks up the combinations this one skipped.

### Failed runs

Every `experiment.toml` sets `continues`, which says what happens to a failed run.

With `continues = false`, a failed run stays as it is, and the next `run` gives its combination a new folder.

With `continues = true`, the next `run` invokes the failed run again in its own folder:

```toml
continues = true
```

`run` takes each failed run in a combination that is short of `repeats` and invokes it again, with the same params and the same `{run_dir}`. A run that fails, is stopped, or was lost when labnotes died all count as failed. Excluded runs and runs that count are left alone and get new folders. A run that exits 75 retries in its folder too.

The folder then holds every invocation. `run.json` lists them under `"invocations"`, each with its own times, exit code, commit, args, labnotes version, and labnotes command line, and each writes its own `stdout-<time>.txt` and `stderr-<time>.txt`. See [`continues`](../api/config#continues) for the fields.

A failed run is invoked again at most `retries` times (3 by default), counting retries after exit 75 but not invocations you stopped. After that it is left alone and its combination stays short. `run --replace-capped` gives that combination a new run, and `run --run-id ID` invokes the capped run once more. See [`retries`](../api/config#retries-1).

Your command finds what its last invocation left in `{run_dir}` and decides what to do with it. labnotes does nothing to those files. In return, your command must never delete `run.json`, `stdout-*`, `stderr-*`, or `run.lock`. labnotes holds a lock on `run.lock` while an invocation runs, and a second `run` skips any run that is locked.

### Run folders

Runs appear on disk as flat folders, each named for the UTC time it was planned:

<Tree>
my-experiment
    runs
        20261020-000429-brave-fox/
        20261020-000431-quiet-river/
</Tree>

Older versions of labnotes nested the runs of one launch inside a shared folder (`runs/20261020-000429-brave-fox/opus-low-1a2b/`). Those runs still list, count toward `repeats`, and show grouped by that folder in the [TUI](tui) and the [frontend](../frontend).

You can use the [TUI](tui) to prioritize and manage which runs are in flight, and concurrency. The [frontend](../frontend) shows progress toward `repeats` for each combination.
