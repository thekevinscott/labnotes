# Working with Experiments

`labnotes` offers a CLI for managing and running experiments. Ensure that you've [first created a configuration file](../getting-started).

## Viewing Experiments

![Browsing experiments: an experiment, an invocation, and a run's output](/demos/experiments.gif)

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

## Running Experiments

You can run an experiment with:

```bash
uvx labnotes experiments foo run
```

By default, this launches the [TUI](tui).

To run an experiment needs a script and parameters defined. This should be defined in an `experiment.toml` file in the experiment folder; it can also be provided on the command line (`uvx labnotes experiments foo run --experiment-config ./foo.toml`).

The TOML file defines the dynamic parameters along with the script to run:

```toml
command = "uv run python run.py --output {run_dir}"
repeats = 5

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

The script can be any command. Each combination of parameters runs `repeats` times. Dynamic parameters will be passed as arguments to the script (`--model opus --effort low`). The script runs from the project root. Each run gets its own run folder; `{run_dir}` in the command becomes that folder's absolute path, so the script knows where to write its output.

Dynamic parameters get recorded for a particular run in a run.json file in the run folder, along with when it started, when it ended, and its exit code. `command` in run.json holds the exact shell command the run executed, with `{run_dir}` and the params filled in. It is written before the run starts, so a run that was killed still has it, and editing `experiment.toml` later doesn't hide what an earlier run did. The script's stdout and stderr are saved alongside. For output too noisy to read raw, such as a model's thinking, the script can write structured blocks with [`log`](../api/sdk#log); they go to `log.jsonl` in the same folder. While the run goes, labnotes samples its memory every 5 seconds into `memory.jsonl`, one JSON line per sample; see [`memory_interval`](../api/config#memory-interval).

labnotes sets `LABNOTES_RUN` to the run folder name in each script's environment. If the script starts a Docker container, label it with `docker run --label "labnotes.run=$LABNOTES_RUN" ...` so labnotes includes that container's active memory in the run's samples. labnotes does not modify the script's Docker commands. Containers without the label are not counted.

Running an experiment opens a TUI that shows a table of all runs. Pending runs are slightly grayed. Runs default to 1 at a time but concurrency can be added with a `--concurrency` flag. The TUI lets you filter runs by a parameter, raise or lower concurrency as runs go, and kill specific runs. Failed runs show in red.

A script that exits 75 (`EX_TEMPFAIL`) is saying it couldn't run for a reason outside the experiment, like no capacity. labnotes retries those on its own with the same params: after 30 seconds, then 60, up to `retries` times (2 by default). Each retry gets its own run folder, linked back by `retry_of` in its `run.json`. Every other non-zero exit is left alone. See [`retries`](../api/config#retries-1).

ctrl-c quits. If runs are going, it asks first: enter (or a second ctrl-c) leaves them running, `s` stops them, and esc goes back.

`--timeout 1800` stops any run still going after 1800 seconds (30 minutes), with SIGTERM and then SIGKILL 5 seconds later. Each run gets its own 30 minutes. Its `run.json` records `"error": "timed out after 30m 00s"`, so a timeout reads differently from a crash.

`run.json` also records why a run ended, in `ended_by`: `"timeout"` for `--timeout`, `"stop"` when labnotes stopped it (`run stop`, `s` at the quit prompt, killing the run in the TUI), `"signal"` when a signal labnotes didn't send ended it, like the kernel's out-of-memory killer, `"lost"` when the process running it died without labnotes noticing (the daemon was killed, the machine rebooted), and `null` when the script exited on its own. `signal` holds the signal number, read from the exit code: a negative code, or 128 plus the number when the shell reports it (137 is SIGKILL, 9). A script that catches a signal and exits with its own code leaves `signal` null, and one that exits 137 on purpose reads as SIGKILL.

The daemon marks lost runs when it starts: an unfinished run whose `pid` is gone, or now belongs to another process, gets `"ended_by": "lost"` and the time it was noticed as `ended`. Its `exit_code` stays `null`, since nobody saw it exit. A run whose process is still alive stays unfinished until a later daemon start finds it gone.
