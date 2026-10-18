# labnotes

Browse experiment designs, notes, and run data from a folder.

```sh
uvx labnotes server
```

A project's root is the folder holding its `.labnotes.toml`. `labnotes init`
writes one with the default layout:

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

Each path is relative to the root. `{experiment}` and `{run}` stand for folder
names: the experiments path must use `{experiment}`, and the runs path both.
labnotes reads the file from the working folder, or from the path given with
`-c`.

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

Each takes `--format table` (the default) or `--format json`.

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
that exit 0 count, so running again fills in what failed or never ran.
Each run gets a new run folder. `command` runs in a shell from the root, with
`{run_dir}` replaced by the run folder's absolute path. Pass it to the
script so it writes its outputs there.
Each param is appended as `--name value`, with the name as written (use
`source-language` for a `--source-language` flag), booleans as 0 or 1, and lists
and tables as JSON. labnotes writes `run.json` (params, created, ended, exit
code), `stdout.log` and `stderr.log` to the run folder.

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

`labnotes server` doesn't read `.labnotes.toml` yet. Give it the two folders
it uses with `--experiments-folder` and `--data-folder`:

- `--experiments-folder` holds one subfolder per experiment, each with a
  `design.yaml` (with a `study` key) and any number of markdown notes.
- `--data-folder` holds the run data and a `.dirsql.toml` that declares a
  `runs` table with a `study` column. An experiment's runs are the rows whose
  `study` matches its design's.

That serves a local site at http://127.0.0.1:8000: a table of experiments,
and a page per experiment with its parameters, its notes, progress per cell of
the design grid, and every run so far. Both folders are watched, so a reload
shows new runs and edited notes.

`design.yaml` keys the site reads: `study`, `fixed`, `varies` (each key a list
of values), `runs_per_cell`, and `completed_run`, a SQL condition over the
`runs` table that marks a run as complete. Anything else shows up as-is.

`-h`/`--host` and `-p`/`--port` change where it listens; `-h 0.0.0.0` (or a
Tailscale IP) serves beyond localhost. Every other uvicorn option passes
through: `--reload`, `--workers`, `--proxy-headers`, `--root-path`, the
`--ssl-*` set, and the rest. `labnotes server --help` lists them. `LABNOTES_EXPERIMENTS_FOLDER` and
`LABNOTES_DATA_FOLDER` can stand in for the folder flags.

## Agent skill

```sh
npx skills add thekevinscott/labnotes
```

The skill tells a coding agent to run `labnotes context`, which prints a usage
guide for the installed version.
