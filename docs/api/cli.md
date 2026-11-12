# CLI

Every command reads `.labnotes.toml` from the working folder.

## Global options

| Option | Description |
| --- | --- |
| `-c, --config FILE` | Read this `.labnotes.toml` instead of the one in the working folder. |
| `--version` | Print the version and exit. |
| `--help` | Print help for any command. |

## `init`

```bash
labnotes init
```

Writes a `.labnotes.toml` with the default layout in the working folder. Refuses to overwrite an existing one.

## `context`

```bash
labnotes context
```

Prints a guide to `labnotes` for coding agents, headed by the config it found and its paths.

## `experiments`

```bash
labnotes experiments [NAME] [runs|run|attach|stop]
```

| Form | Does |
| --- | --- |
| `labnotes experiments` | Lists experiments: name, last run, created, files, runs, live daemon and running cell count. |
| `labnotes experiments NAME` | Shows one experiment, plus its config. |
| `labnotes experiments NAME runs` | Lists the experiment's runs, oldest first, with each run's `memory` and `size`. |
| `labnotes experiments NAME run` | Runs the experiment in the [TUI](tui). Requires stdout and stderr to be terminals. |
| `labnotes experiments NAME attach` | Reopens the run [TUI](tui) on whatever the experiment's daemon is running, including restarts. Starts nothing: with nothing running it says so and exits. Any number of TUIs can attach at once, and every control acts on the daemon, so all of them see the result. |
| `labnotes experiments NAME stop` | Asks the live daemon to stop all its cells. Exits non-zero with a clear message if no daemon is live. Daemons are keyed by the installed labnotes version, so after an upgrade or downgrade `stop` cannot see or stop a daemon started by the old version. |
| `labnotes experiments new [NAME]` | Creates an experiment folder and writes its `experiment.toml`, from the starter or from `--from OTHER`, with any `--command`, `--param` and `--repeats` written in. Picks a random name if you give none. Refuses a folder that already exists. |

With `--format` unset, the three listing forms open the [browser](tui#browsing) when stdout and stderr are both a terminal, starting on the experiment if you name one. Otherwise they print a table.

| Option | Description |
| --- | --- |
| `--format table\|json` | Print the listing forms in this format and exit, even in a terminal. No default. |
| `--concurrency N` | With `run`: how many runs at once. Overrides `experiment.toml` and `.labnotes.toml`; 1 if none sets it. |
| `-e, --experiment-config FILE` | With `run`: read this file instead of the experiment's `experiment.toml`. |
| `--PARAM=VALUE` | With `run`: run only the cells where that param has that value, like `--model=small`. PARAM must be a key in `[params]` and VALUE one of its values, written as `runs` shows it (`true`, `2`). Repeat a param to run any of several values (`--model=small --model=large`); different params narrow further. Counts, progress and `repeats` still cover every cell. |
| `-- ARGS` | With `run`: append ARGS to every run's command, after the params, like `-- --auth api`. Each run's `run.json` records them as `args` and in `command`. Use it for per-launch settings that aren't part of the design or a matrix axis; runs started with different ARGS still count toward the same cells. A flag already in the command overrides it in place: with `command = "study --memory 8g --out {run_dir}"`, `-- --memory 24g` runs `study --memory 24g --out ...`, and `--memory=8g` in the command stays in that form. A flag the command lacks is appended. A flag followed by a word that doesn't start with `-` takes that word as its value, so write a value that starts with `-` as `--flag=-1`. A flag given without a value that the command already has leaves the command alone. A flag that names a param, one the command has more than once, or one ARGS give more than once to override the command is an error. ARGS are written to disk as given, so never pass secrets. |
| `--command COMMAND` | With `new`: the experiment's [`command`](config#command). |
| `--param NAME=VALUE` | With `new`: a value for [`params`](config#params). Repeat it for several values, like `--param model=opus --param model=sonnet`. VALUE is taken whole, commas included, and parsed as TOML, falling back to a string: `3` is a number, `"3"` and `opus` are strings. |
| `--repeats N` | With `new`: the experiment's [`repeats`](config#repeats). |
| `--from OTHER` | With `new`: start from experiment OTHER. Copies its folder, `experiment.toml` and files, but never its runs, and records [`from`](config#from) in the new `experiment.toml`. `--command` and `--repeats` replace the copied values; `--param NAME=...` replaces that param's values and leaves the other params as copied. Comments in the copied file are kept. A copied `mode` is dropped, and a copy without `continues` gets the project's [`continues`](config#continues) default, else `continues = false`. |
| `--retries N` | With `run`: how many times a failed run is tried again, on a [retry exit code](config#retry-exit-codes-1) or, with `continues`, by a later `run`. Overrides [`retries`](config#retries-1) in `experiment.toml` and `.labnotes.toml`; 3 if none sets it. |
| `--retry-wait SECONDS` | With `run`: seconds before the first retry; each later retry waits twice as long. Overrides [`retry_wait`](config#retry-wait-1) in `experiment.toml` and `.labnotes.toml`; 30 if none sets it. |
| `--retry-exit-code CODE` | With `run`: an exit code, 1 to 255, that earns a retry. Repeat it for several. Overrides [`retry_exit_codes`](config#retry-exit-codes-1) in `experiment.toml` and `.labnotes.toml`; 75 if none sets it. |
| `--replace-capped` | With `run`: start a fresh run for each cell whose failed run is out of `retries`. Unset, that cell stays short. |
| `--setup COMMAND` | With `run`: shell command to run once before any run starts. Overrides [`setup`](config#setup) in `experiment.toml` and `.labnotes.toml`. |
| `--teardown COMMAND` | With `run`: shell command to run once after every run ends. Overrides [`teardown`](config#teardown) in `experiment.toml` and `.labnotes.toml`. |
| `--timeout SECONDS` | With `run`: stop any one run still going after this many seconds, with SIGTERM, then SIGKILL after five seconds. Takes a whole number over 0, like `600`. No default: unset, runs have no time limit. |

`new` only writes `experiment.toml`; nothing it is given is stored anywhere else. Hooks, `[env]` and `counts` are set by editing the file. For example:

```bash
labnotes experiments new sanity-3 \
  --command "uv run python run.py --out {run_dir}" \
  --param model=opus --param model=sonnet \
  --repeats 3

labnotes experiments new sanity-4 --from sanity-3 --param model=haiku
```

`run` exits after printing `N passed, M failed.`, plus `K retried.` when runs were retried. A retried run counts as retried, not failed. A run whose command exits 75, or another code in [`retry_exit_codes`](config#retry-exit-codes-1), is retried on its own; see [`retries`](config#retries-1).

Runs execute in a background daemon, not in your terminal. Each run's command, and `setup`, `meta` and `teardown`, get `/dev/null` as stdin, so a command that reads input sees end of file at once.

In the runs listing, `memory` is the resident memory of a running run's command and everything it started, and `size` is what its run folder holds on disk, hidden files and folders aside. A symlink to a file counts as its target's size; symlinked folders aren't followed. A finished run has a size and no memory. The table shows them like `3.2 GB`; `--format json` gives bytes, with `null` where there's nothing to show. The command's process id is in the run's `run.json` as `pid`, with its start time as `pid_created`; memory is only read while that process is the same one and the record hasn't ended, so a reused pid after a crash shows no memory.

Each run's `run.json` also records `git`: `{"commit": "<full HEAD SHA>", "dirty": false}`, taken from the invocation's snapshot when the invocation starts. `dirty` counts staged and unstaged changes to tracked files, plus untracked files that are not ignored. Every run in the invocation, including a queued run or a retry, records that start commit, even if the project's HEAD has moved since. `git` is `null` outside a Git repository, when Git is unavailable, or if the lookup fails (including a repository with no commits). Older records lack this key.

Each run's `run.json` also records `labnotes_version`, the installed labnotes version that ran it, and `labnotes_command`, the labnotes command line that started it, like `"labnotes -c .labnotes.toml experiments exp run --model=small -- --auth api"`. The command line holds the `-- ARGS` too, so the same rule applies: never pass secrets. Older records lack these keys.

A run stopped by `--timeout 600` records `"error": "timed out after 10m 00s"` in its `run.json`, next to the exit code it ended with, and `"ended_by": "timeout"`. The live TUI and the run's web page show that error in place of the exit code, and it counts as failed.

## `server`

```bash
labnotes server [OPTIONS]
```

Serves the [frontend](../frontend).

| Option | Description |
| --- | --- |
| `-h, --host TEXT` | Bind to this host. Default `127.0.0.1`. `0.0.0.0` or a Tailscale IP serves beyond localhost. |
| `-p, --port INTEGER` | Default `8000`. |

Every other [uvicorn option](https://www.uvicorn.org/settings/) works too, such as `--reload` or `--uds`.
