# labnotes

`labnotes` helps you manage your experiments.

## Getting Started

You can use `labnotes` without installation:

```bash
uvx labnotes
```

`labnotes` is designed to work entirely with local files.


`labnotes` organizes its data largely by _folder_; folders structure how it views files. (Config can overrule these but this will be the default.)

Let's say you have the following structure:

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

You'll want to define a configuration file mapping your files to a SQL layout; start by defining a config file:

```bash
uvx labnotes init
```

`labnotes` will automatically pick up `.labnotes.toml` when run from the same folder, or specify it with `uvx labnotes -c /path/to/.labnotes.toml`.

`init` maps the structure above to three SQL tables, `experiments`, `files`, and `runs`:

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

Change the paths to match how your files are organized.

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

Running an experiment opens a TUI that shows a table of all runs. Pending runs are slightly grayed. Runs default to 1 at a time but concurrency can be added with a `--concurrency` flag. The TUI lets you filter runs by a parameter, raise or lower concurrency as runs go, and kill specific runs. Failed runs show in red.

ctrl-c quits. If runs are going, it asks first: enter (or a second ctrl-c) stops them, `s` also stops them, and esc goes back.

## Skill

You can install the `labnotes` skill with:

```bash
npx skills add thekevinscott/labnotes
```

Agents start runs in a dedicated tmux window and watch the live table there. Closing the window stops the runs.

## Frontend

There's a frontend for interacting with `labnotes`:

```bash
uvx labnotes server
```

Pass `--host` and `--port` as CLI vars and every other uvicorn option.

## Example Organizations

Three paths in `.labnotes.toml` say where experiments, files and runs live. Two layouts cover most projects:

- One Folder, One Experiment: each experiment is a folder, with its notes in `files` and its runs in `runs`. `uvx labnotes init` writes this one.
- One Run Tree, Many Experiments: notes stay with each experiment, and all runs go in one `runs` tree with a folder per experiment.

[Common Organizations](docs/guides/common-organizations.md) shows both, with the config for each.
