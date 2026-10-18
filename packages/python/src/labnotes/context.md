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
  `error`, `stdout`, `stderr`, and `params` as JSON, read from each run
  folder's `run.json`.

Keys come from folder names, so renaming a folder renames its rows on the next
read. Paths are relative to the root, and times are UTC ISO 8601.

```sh
labnotes experiments            # name, last_run, created, files, runs
labnotes experiments foo        # the same, plus config
labnotes experiments foo runs   # foo's runs, oldest first
```

Each takes `--format table` (the default) or `--format json`; use `--format json` when you parse the output.

`labnotes experiments foo run` runs `foo` from its `experiment.toml`, in the
experiments folder:

```toml
command = "uv run scripts/study.py --output {run_dir}"
repeats = 5

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

Each combination of `[params]` runs `repeats` times, round-robin. Only runs
that exit 0 count, so running again fills in what failed or never ran.
Each run gets a new run folder. `command` runs in a shell from the root, with
`{run_dir}` replaced by the run folder's absolute path. Pass it to the
script so it writes its outputs there.
Each param is appended as `--name value`, with the name as written (use
`source-language` for a `--source-language` flag), booleans as 0 or 1, and lists
and tables as JSON. labnotes writes `run.json` (params, created, ended, exit
code), `stdout.log` and `stderr.log` to the run folder.

A script run by labnotes should:

- take each param as a `--name value` flag, parsing lists and tables from JSON;
- take its output folder as an argument, passed in `command` as `{run_dir}`, and write everything it produces there;
- exit non-zero when it fails, so the run counts as failed and runs again next time.

Runs can take a long time. Start `run` in the background, then check on it with `labnotes experiments foo runs`; a run with no `ended` is still going.

In a terminal, `run` shows a live table of runs (status and time) and stays
open when they finish; `q` quits. Elsewhere, or with `--no-tui`, it prints a
line per event instead.

- `--concurrency N` runs N at a time (default 1).
- `-e PATH` reads another file instead of `experiment.toml`.
- Ctrl-C stops the running scripts and records their end. A second Ctrl-C
  kills them. Closing the terminal or sending SIGTERM stops them the same way,
  then kills any still going 5 seconds later.
- A second `run` of the same experiment fails while the first holds the lock.
- It exits 1 if any run failed.

`labnotes server` doesn't read `.labnotes.toml` yet: pass `--experiments-folder` and `--data-folder`, or set `LABNOTES_EXPERIMENTS_FOLDER` and `LABNOTES_DATA_FOLDER`. The experiments folder has one subfolder per experiment, each with a `design.yaml` and markdown notes. The data folder holds run data and a `.dirsql.toml` declaring a `runs` table with a `study` column.

The run data lives in the data folder. Query it with [dirsql](https://dirsql.dev) and the data folder's `.dirsql.toml`, which declares the `runs` table:

```sh
uvx dirsql -c data/.dirsql.toml "SELECT * FROM runs LIMIT 1" --format json
```

`uvx labnotes server` serves the experiments and their runs as a local site.
