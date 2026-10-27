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
labnotes experiments [NAME] [runs|run]
```

| Form | Does |
| --- | --- |
| `labnotes experiments` | Lists experiments: name, last run, created, files, runs. |
| `labnotes experiments NAME` | Shows one experiment, plus its config. |
| `labnotes experiments NAME runs` | Lists the experiment's runs, oldest first, with each run's `memory` and `size`. |
| `labnotes experiments NAME run` | Runs the experiment. Opens the [TUI](tui) in a terminal; otherwise prints a line per event and blocks until the runs end. |
| `labnotes experiments new [NAME]` | Creates an experiment folder with a starter `experiment.toml`. Picks a random name if you give none. |

With `--format` unset, the three listing forms open the [browser](tui#browsing) when stdout and stderr are both a terminal, starting on the experiment if you name one. Otherwise they print a table.

| Option | Description |
| --- | --- |
| `--format table\|json` | Print the listing forms in this format and exit, even in a terminal. No default. |
| `--concurrency N` | With `run`: how many runs at once. Overrides `experiment.toml` and `.labnotes.toml`; 1 if none sets it. |
| `-e, --experiment-config FILE` | With `run`: read this file instead of the experiment's `experiment.toml`. |
| `--PARAM=VALUE` | With `run`: run only the cells where that param has that value, like `--model=small`. PARAM must be a key in `[params]` and VALUE one of its values, written as `runs` shows it (`true`, `2`). One value per param; several params narrow further. Counts, progress and `repeats` still cover every cell. |
| `-- ARGS` | With `run`: append ARGS to every run's command, after the params, like `-- --auth api`. Each run's `run.json` records them as `args` and in `command`. Use it for per-launch settings that aren't part of the design or a matrix axis; runs started with different ARGS still count toward the same cells. A flag that names a param or one already in the command is an error. ARGS are written to disk as given, so never pass secrets. |
| `--timeout SECONDS` | With `run`: stop any one run still going after this many seconds, the same way as [`run stop`](#run-stop). Takes a whole number over 0, like `600`. No default: unset, runs have no time limit. |

`run` exits after printing `N passed, M failed.`, plus `K retried.` when runs were retried. A retried run counts as retried, not failed. A run whose command exits 75 is retried on its own; see [`retries`](config#retries-1).

In the runs listing, `memory` is the resident memory of a running run's command and everything it started, and `size` is what its run folder holds on disk, hidden files and folders aside. A symlink to a file counts as its target's size; symlinked folders aren't followed. A finished run has a size and no memory. The table shows them like `3.2 GB`; `--format json` gives bytes, with `null` where there's nothing to show. The command's process id is in the run's `run.json` as `pid`, with its start time as `pid_created`; memory is only read while that process is the same one and the record hasn't ended, so a reused pid after a crash shows no memory.

A run stopped by `--timeout 600` records `"error": "timed out after 10m 00s"` in its `run.json`, next to the exit code it ended with, and `"ended_by": "timeout"`. The live TUI and the run's web page show that error in place of the exit code, and it counts as failed.

## `run`

Controls the runs going in the project. Runs belong to the project's daemon, so these work from any shell.

### `run status`

```bash
labnotes run status [-f] [--json]
```

Shows what each experiment is running, the latest line each running run logged, and what each running run uses, like `exp: r1 uses 3.2 GB of memory, 5.2 GB on disk.` Memory is the resident memory of the run's command and everything it started. With `-f`, the usage repeats every 30 seconds. When a run fails, its end line carries the last non-blank line of its `stderr.log`, like `exp: r1 exited 1: ValueError: boom`.

| Option | Description |
| --- | --- |
| `-f, --follow` | Keep reporting until interrupted. |
| `--json` | One JSON event per line. Retries show as `retrying` (with `attempt`, `retries` and `seconds`), `retried`, `gave up` and `retry cancelled`. Usage shows as `usage`, with `memory` and `size` in bytes. A failed run's `ended` event adds `last_stderr`. |

### `run stop`

```bash
labnotes run stop
```

Stops every run. Scripts get SIGTERM, then SIGKILL 5 seconds later. Each stopped run's `run.json` records `"ended_by": "stop"`, so it reads apart from a run something else killed (`"ended_by": "signal"`).

### `run control`

```bash
labnotes run control NAME ACTION [ARG]
```

Sends one control to an experiment's runs, the same as a [TUI](tui) key.

| Action | Argument | Does |
| --- | --- | --- |
| `kill` | run | Stops a running run. A second `kill` kills it. On a run waiting to retry, cancels the retry. |
| `set_concurrency` | number | Sets how many run at once. |
| `finish` | | Lets running runs finish and starts no more. |
| `interrupt` | | Stops every running run. |

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
