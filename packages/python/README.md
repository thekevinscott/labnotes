# labnotes

Browse experiment designs, notes, and run data from a folder.

```sh
uvx labnotes
```

labnotes reads two folders, named in a `labnotes.toml` at the project root:

```toml
experiments = "experiments"
data = "data"
```

Both keys are optional and default to the values above. Paths are relative to
`labnotes.toml`, or absolute, or start with `~`. labnotes looks for the file in
the working folder and then each parent.

- `experiments` holds one subfolder per experiment, each with a
  `design.yaml` (with a `study` key) and any number of markdown notes.
- `data` holds the run data and a `.dirsql.toml` that declares a
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
`--ssl-*` set, and the rest. `labnotes --help` lists them. `--experiments-folder`
and `--data-folder`, or `LABNOTES_EXPERIMENTS_FOLDER` and
`LABNOTES_DATA_FOLDER`, override `labnotes.toml`. `--json`
prints the experiments as JSON and exits.

## From the command line

Name an experiment to print what has run for it as JSON. Add SQL to query
that experiment's runs: `runs` holds only its runs, `main.runs` every run.

```sh
uvx labnotes models-effort "SELECT model, COUNT(*) AS n FROM runs GROUP BY 1"
```

## Agent skill

```sh
npx skills add thekevinscott/labnotes
```

The skill tells a coding agent to run `labnotes context`, which prints a usage
guide for the installed version.
