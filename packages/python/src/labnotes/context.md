## Usage

A project that uses labnotes has a `.labnotes.toml` at its root; the folder holding it is the root. labnotes reads it from the working folder, so run labnotes from the project root, or pass `-c PATH`. The lines above this guide name the one found and its paths, or say there is none. `labnotes init` writes one with the default layout:

```toml
[experiments]
path = "{experiment}"            # one folder per experiment

[files]
path = "{experiment}/files/"     # an experiment's notes and other files

[runs]
path = "{experiment}/runs/{run}" # one folder per run
```

Paths are relative to the root. `{experiment}` and `{run}` stand for folder names; the experiments and files paths use `{experiment}`, the runs path both. A project laid out differently keeps its folders and changes the paths: look at where its experiments, notes and runs live, then write the templates that match.

`labnotes experiments` reads three tables from those paths:

- `experiments`: `name`, and `config`, the experiment's `experiment.toml` as
  JSON. An experiment is a folder matching the experiments path that holds an
  `experiment.toml`, files or runs.
- `files`: `experiment`, `filename`, `path`, `ctime`, `mtime`.
- `runs`: `experiment`, `id`, `folder`, `created`, `ended`, `exit_code`,
  `error`, `stdout`, `stderr`, `params` as JSON, and `run`, the whole
  `run.json` as JSON, read from each run folder's `run.json`.

Keys come from folder names, so renaming a folder renames its rows on the next
read. Paths are relative to the root, and times are UTC ISO 8601.

```sh
labnotes experiments            # name, last_run, created, files, runs
labnotes experiments foo        # the same, plus config
labnotes experiments foo runs   # foo's runs, oldest first
```

Each takes `--format table` (the default) or `--format json`; use `--format json` when you parse the output.

`labnotes experiments new [NAME]` creates an experiment folder with a starter
`experiment.toml`, picking a random name if you give none. `new` itself can't
be an experiment name.

`labnotes experiments foo run` runs `foo` from its `experiment.toml`, in the
experiments folder:

```toml
name = "Model and effort"
command = "uv run scripts/study.py --output {run_dir}"
repeats = 5

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

`name` is optional: a display name for the experiment, shown in the live view
and as `display_name` in `experiments`. The folder name stays the key, so
renaming the experiment means editing `name`.
Each combination of `[params]` runs `repeats` times, round-robin. Only runs
that count fill a combination, so running again fills in what failed or never
ran.
Each run gets a new run folder. `command` runs in a shell from the root, with
`{run_dir}` replaced by the run folder's absolute path. Pass it to the
script so it writes its outputs there.
Each param is appended as `--name value`, with the name as written (use
`source-language` for a `--source-language` flag), booleans as 0 or 1, and lists
and tables as JSON. labnotes writes `run.json` (params, created, ended, exit
code, and `invocation_id`, shared by every run one `run` command started;
query it as `run ->> 'invocation_id'`), `stdout.log` and `stderr.log` to the
run folder.
A run counts when it exited 0 and its `run.json` doesn't hold
`"excluded": true`, so excluding a run by hand means adding that key; the next
`run` replaces it. Other keys you add to `run.json` are kept and show in `run`.
`counts` in `experiment.toml` replaces the rule with a SQL condition over
`runs`, for example `counts = "exit_code = 0 AND created > '2026-10-01'"` to
drop runs from before a script change. The default is
`exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)`.
`experiments foo runs` shows the rule's result as `counted`; queries over
`runs` itself see every run, so apply the rule there too.

A script run by labnotes should:

- take each param as a `--name value` flag, parsing lists and tables from JSON;
- take its output folder as an argument, passed in `command` as `{run_dir}`, and write everything it produces there;
- exit non-zero when it fails, so the run counts as failed and runs again next time;
- stop any background process it starts before it exits; the run ends when `command` exits.
- flush its output as it goes (`print(..., flush=True)`, or `PYTHONUNBUFFERED=1`), so the live view shows it as it happens.

Runs can take a long time. Start `run` in the background, then check on it with `labnotes experiments foo runs`; a run with no `ended` is still going.

In a terminal, `run` shows a live table of runs (status and time) and stays
open when they finish. Failed runs show their status in red; `h` hides or shows them, and `r` on one
runs it again under a new id. Runs not started yet show grayed as `pending`, and as
`skipped` once stopped. Move the cursor to a pending run and press `n` to run it
next. `d` deselects a pending run so it won't run; `d` again puts it back at
the end of the queue. `/` filters rows by params text; Enter keeps the filter,
Escape clears it. `D` deselects every pending run the filter shows. `k` stops the
running run under the cursor; `k` again kills it. `+` and
`-` change how many run at once; lowering it lets running runs
finish. Enter on a run follows its `stdout.log`; `e` switches to
`stderr.log` and back, and Escape returns to the table. `q` quits. Elsewhere, or with `--no-tui`, it prints a
line per event instead.

- `--concurrency N` runs N at a time to start with (default 1).
- `-e PATH` reads another file instead of `experiment.toml`.
- Ctrl-C stops the running scripts and records their end. A second Ctrl-C
  kills them. Closing the terminal or sending SIGTERM stops them the same way,
  then kills any still going 5 seconds later. Once the runs are done, either
  one closes the live view.
- A second `run` of the same experiment fails while the first holds the lock.
- It exits 1 if any run failed.

`uvx labnotes server` serves the experiments, their markdown files and their runs as a local site, read from the same `.labnotes.toml`. A grid cell is full once it has `repeats` runs that count.
