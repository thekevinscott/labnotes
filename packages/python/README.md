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

`labnotes experiments foo run` runs `foo` from its `experiment.toml`, in the
experiments folder:

```toml
command = "uv run run-study"
repeats = 5

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

Each combination of `[params]` runs `repeats` times, round-robin. Only runs
that exit 0 count, so running again fills in what failed or never ran.
`command` runs in a shell, inside a new run folder, so give it absolute paths
or commands on `PATH`. Each param is appended as `--name value`, with the
name as written (use `source-language` for a `--source-language` flag),
booleans as 0 or 1, and lists and tables as JSON. labnotes writes `run.json` (params, created, ended, exit code) and
captures `stdout.log` and `stderr.log` there.

- `--concurrency N` runs N at a time (default 1).
- `-e PATH` reads another file instead of `experiment.toml`.
- Ctrl-C stops the running scripts and records their end. A second Ctrl-C
  kills them.
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
