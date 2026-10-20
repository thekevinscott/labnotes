# Config

Assume you have the following structure on disk:

```
/data
  /experiment-one
    /files
      /readme.md
      /plan.md
    /runs
  /experiment-two
    /files
      /readme.md
    /runs
```

You can define a configuration file mapping your files to a SQL layout. `init` will create a config file:

```bash
uvx labnotes init
```

`labnotes` will automatically pick up `.labnotes.toml` when run from the same folder, or specify it with `uvx labnotes -c /path/to/.labnotes.toml`.

labnotes reads two kinds of TOML file: one `.labnotes.toml` per project, and one `experiment.toml` per experiment. 

## `.labnotes.toml`

Must be at the project root. 

[experiments]
path = "{experiment}"            # one folder per experiment
mode = "adhoc"                   # default for every experiment
concurrency = 1                  # default for every experiment

[files]
path = "{experiment}/files/"     # an experiment's notes and other files

[runs]
path = "{experiment}/runs/{run}" # one folder per run
```

| Key | Default | Meaning |
| --- | --- | --- |
| `[experiments] path` | `"{experiment}"` | Where experiment folders live. Must use `{experiment}`. |
| `[experiments] mode` | `"adhoc"` | `"adhoc"` or `"fill"`, for experiments that don't set their own. |
| `[experiments] concurrency` | `1` | Runs at once, for experiments that don't set their own. |
| `[files] path` | `"{experiment}/files/"` | Where an experiment's notes and files live. Must use `{experiment}`. |
| `[runs] path` | `"{experiment}/runs/{run}"` | Where run folders live. Must use `{experiment}` and `{run}`. |

Paths are relative to the root. Absolute paths and `~` are rejected.

## `experiment.toml`

One per experiment folder. `labnotes experiments new [NAME]` creates one.

```toml
name = "Model and effort"
command = "uv run scripts/study.py --output {run_dir}"
repeats = 5
mode = "fill"
concurrency = 2
counts = "exit_code = 0 AND created > '2026-10-01'"

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

| Key | Default | Meaning |
| --- | --- | --- |
| `command` | required | Shell command for one run, run from the root. `{run_dir}` becomes the run folder's absolute path. |
| `name` | folder name | Display name. The folder name stays the key. |
| `repeats` | `1` | Runs per combination of params. |
| `[params]` | none | Each key is a non-empty list. Every combination runs. Each value is passed as `--name value`; booleans as 0 or 1, lists and tables as JSON. |
| `mode` | from `.labnotes.toml`, else `"adhoc"` | `"adhoc"`: every `run` plans the full grid. `"fill"`: `run` plans only combinations short of `repeats` counted runs. |
| `concurrency` | from `.labnotes.toml`, else `1` | Runs at once. `--concurrency` on the command line wins. |
| `counts` | `exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)` | SQL condition over `runs` that decides which runs count toward `repeats`. |
