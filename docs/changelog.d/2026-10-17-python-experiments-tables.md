**Added** — `labnotes experiments [NAME] [runs]` lists experiments, one
experiment with its config, or an experiment's runs, as a table or with
`--format json`. It reads built-in `experiments`, `files` and `runs` tables
with dirsql from the path templates in `.labnotes.toml`. A run is a folder
holding a `run.json`.
