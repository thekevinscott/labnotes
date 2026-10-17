## Usage

labnotes reads two folders. The experiments folder has one subfolder per experiment, each with a `design.yaml` and markdown notes. The data folder holds run data and a `.dirsql.toml` declaring a `runs` table with a `study` column. A project that uses labnotes has a `.labnotes.toml` at its root; labnotes reads it from the working folder, so run labnotes from the project root, or pass `-c PATH`. The lines above this guide name the one found and the folders it resolves to, or say there is none. Its keys are optional:

```toml
experiments = "experiments"  # the default
data = "data"                # relative to .labnotes.toml, absolute, or ~
```

`--experiments-folder` and `--data-folder`, or `LABNOTES_EXPERIMENTS_FOLDER` and `LABNOTES_DATA_FOLDER`, override either key. Without a `.labnotes.toml`, pass both.

The run data lives in the data folder. Query it with [dirsql](https://dirsql.dev) and the data folder's `.dirsql.toml`, which declares the `runs` table:

```sh
uvx dirsql -c data/.dirsql.toml "SELECT * FROM runs LIMIT 1" --format json
```

`uvx labnotes server` serves the experiments and their runs as a local site.
