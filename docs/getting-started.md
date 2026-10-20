# labnotes

`labnotes` helps you manage your experiments.

## Getting Started

You can use `labnotes` without installation:

```bash
uvx labnotes
```

Read a bit [about the `labnotes` philosophy](philosophy). You can also read about how to [configure your filesystem](config) to work with `labnotes`.

`labnotes` offers the following surfaces:

- a [TUI](tui), for running experiments
- a [frontend](frontend), for analyzing experiments


## CLI

All commands take a `--format` flag, with `table` (default) and `json`.

View experiments with:

```bash
uvx labnotes experiments
```

Which returns name, last run, created, files (num), runs (num). 

View a particular experiment with:

```bash
uvx labnotes experiments foo
```

Which shows metadata about the experiment along with the above fields. You can see runs with:

```bash
uvx labnotes experiments foo runs
```

You can run an experiment with:

```bash
uvx labnotes experiments foo run
```

To run an experiment needs a script and parameters defined. This should be defined in an `experiment.toml` file in the experiment folder; it can also be provided on the command line (`uvx labnotes experiments foo run --experiment-config ./foo.toml`).

The TOML file defines the dynamic parameters along with the script to run:

```toml
command = "uv run python run.py --output {run_dir}"
repeats = 5

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

The script can be any command. Each combination of parameters runs `repeats` times. Dynamic parameters will be passed as arguments to the script (`--model opus --effort low`). The script runs from the project root. Each run gets its own run folder; `{run_dir}` in the command becomes that folder's absolute path, so the script knows where to write its output.

Dynamic parameters get recorded for a particular run in a run.json file in the run folder, along with when it started, when it ended, and its exit code. The script's stdout and stderr are saved alongside.

Running an experiment opens a TUI that shows a table of all runs. Pending runs are slightly grayed. Runs default to 1 at a time but concurrency can be added with a `--concurrency` flag. The TUI allows you to queue specific runs to go next, or filter by a parameter and deselect pending runs so they don't run. You can also raise or lower concurrency dynamically. You can also kill specific runs. Failed runs show in red; you can retry them or hide them.

ctrl-c stops all runs and cleans up. A second ctrl-c kills them immediately.

## Skill

You can install the `labnotes` skill with:

```bash
npx skills add thekevinscott/labnotes
```

## Frontend

There's a frontend for interacting with `labnotes`:

```bash
uvx labnotes server
```

Pass `--host` and `--port` as CLI vars and every other uvicorn option.

## Example Organizations

### Default

```
/experiment-one
  /files
    /readme.md
  /runs
```

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

### Notes next to the runs

```
/experiment-one
  /readme.md
  /plan.md
  /results
```

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/*.md"

[runs]
path = "{experiment}/results/{run}"
```

### Notes and runs in separate trees

```
/notes
  /experiment-one
    /readme.md
/data
  /experiment-one
```

```toml
[experiments]
path = "notes/{experiment}"

[files]
path = "notes/{experiment}/*.md"

[runs]
path = "data/{experiment}/{run}"
```
