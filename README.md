# labnotes

Browse experiment designs, notes, and run data from a folder.

```sh
uvx labnotes --experiments-folder experiments --data-folder data
```

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

`--host` and `--port` change where it listens. `--json` prints the experiments
as JSON and exits.
