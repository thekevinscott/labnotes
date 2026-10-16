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
