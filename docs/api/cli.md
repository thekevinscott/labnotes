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
| `labnotes experiments NAME runs` | Lists the experiment's runs, oldest first. |
| `labnotes experiments NAME run` | Runs the experiment. Opens the [TUI](tui) in a terminal; otherwise prints a line per event and blocks until the runs end. |
| `labnotes experiments new [NAME]` | Creates an experiment folder with a starter `experiment.toml`. Picks a random name if you give none. |

With `--format` unset, the three listing forms open the [browser](tui#browsing) when stdout and stderr are both a terminal, starting on the experiment if you name one. Otherwise they print a table.

| Option | Description |
| --- | --- |
| `--format table\|json` | Print the listing forms in this format and exit, even in a terminal. No default. |
| `--concurrency N` | With `run`: how many runs at once. Overrides `experiment.toml` and `.labnotes.toml`; 1 if none sets it. |
| `-e, --experiment-config FILE` | With `run`: read this file instead of the experiment's `experiment.toml`. |
| `--timeout SECONDS` | With `run`: stop any one run still going after this many seconds, the same way as [`run stop`](#run-stop). Takes a whole number over 0, like `600`. No default: unset, runs have no time limit. |

`run` exits after printing `N passed, M failed.`, plus `K retried.` when runs were retried. A retried run counts as retried, not failed. A run whose command exits 75 is retried on its own; see [`retries`](config#retries-1).

A run stopped by `--timeout 600` records `"error": "timed out after 10m 00s"` in its `run.json`, next to the exit code it ended with, and `"ended_by": "timeout"`. The live TUI and the run's web page show that error in place of the exit code, and it counts as failed.

## `run`

Controls the runs going in the project. Runs belong to the project's daemon, so these work from any shell.

### `run status`

```bash
labnotes run status [-f] [--json]
```

Shows what each experiment is running and the latest line each running run logged.

| Option | Description |
| --- | --- |
| `-f, --follow` | Keep reporting until interrupted. |
| `--json` | One JSON event per line. Retries show as `retrying` (with `attempt`, `retries` and `seconds`), `retried`, `gave up` and `retry cancelled`. |

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
| `run_next` | run | Runs this pending run next. |
| `toggle` | run | Deselects a pending run, or puts it back. |
| `move` | run, place | Moves a pending run to that place in the queue, counted from 0. |
| `kill` | run | Stops a running run. A second `kill` kills it. On a run waiting to retry, cancels the retry. |
| `retry` | run | Runs a failed run again under a new id, with `retry_of` in its `run.json`. On a run waiting to retry, starts the retry now. |
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
