## Usage

labnotes reads two folders. The experiments folder has one subfolder per experiment, each with a `design.yaml` and markdown notes. The data folder holds run data and a `.dirsql.toml` declaring a `runs` table with a `study` column. Pass both on every call, or set `LABNOTES_EXPERIMENTS_FOLDER` and `LABNOTES_DATA_FOLDER`:

```sh
uvx labnotes --experiments-folder experiments --data-folder data --json
```

`--json` lists every experiment: its name, study, the design's fixed and varied conditions, the target run count, and how many runs have run and completed, overall and per cell.

### One experiment

Name an experiment to see what has run for it, as JSON:

```sh
uvx labnotes models-effort --experiments-folder experiments --data-folder data
```

Add SQL to query its runs. `runs` holds only that experiment's runs, matched on the study in its `design.yaml`; `main.runs` holds every run in the data folder. The query goes through [dirsql](https://dirsql.dev), so it is SQLite and read-only:

```sh
uvx labnotes models-effort "SELECT model, effort, COUNT(*) AS n FROM runs GROUP BY 1, 2" --experiments-folder experiments --data-folder data
```

stdout is one JSON array of row objects. The columns are whatever the data folder's `.dirsql.toml` declares; `SELECT * FROM runs LIMIT 1` shows them. A run counts as completed when the design's `completed_run` SQL expression is true; the one-experiment JSON prints it, so reuse it in a `WHERE`.

An unknown experiment, an experiment without a `study`, or bad SQL prints an error to stderr and exits `1`. An experiment named `context` cannot be queried this way.
