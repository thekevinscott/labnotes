# Config

labnotes reads two kinds of TOML file: one `.labnotes.toml` per project, and one `experiment.toml` per experiment. Unknown tables, unknown keys and invalid TOML are errors.

## `.labnotes.toml`

Must be at the project root; the folder holding it is the root. labnotes reads it from the working folder, or from `-c PATH`. `labnotes init` writes one with the defaults below and refuses to overwrite an existing file.

```toml
[experiments]
path = "{experiment}"
concurrency = 1
retries = 3

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

Paths are relative to the root. Absolute paths and `~` are rejected.

### One experiment

When `experiment.toml` sits next to `.labnotes.toml`, or `.labnotes.toml` has an [`[experiment]`](#experiment) table and no `[experiments] path`, the root is the project's one experiment. Its name is the root folder's name; `name` in `experiment.toml` stays the display name. Paths can't use `{experiment}` and `[experiments] path` is rejected; `concurrency`, `retries`, `retry_wait` and `retryable` still apply. The defaults become:

```toml
[files]
path = "files/"

[runs]
path = "runs/{run}"
```

`labnotes init` writes these when it finds an `experiment.toml`. `labnotes experiments new` refuses, since the root can't hold other experiments.

### `[experiments]`

#### `path`

- Type: string
- Default: `"{experiment}"`
- Placeholders: `{experiment}`, required

Where experiment folders live. An experiment is a matching folder that holds an `experiment.toml`, files or runs.

#### `concurrency`

- Type: positive integer
- Default: `1`

Runs at once for every experiment whose `experiment.toml` doesn't set it.

#### `retries`

- Type: integer, 0 or more
- Default: `3`

Retries for a failed run, for every experiment whose `experiment.toml` doesn't set it. See [`retries`](#retries-1).

#### `retry_wait`

- Type: number of seconds, 0 or more
- Default: `30`

Seconds before the first retry, for every experiment whose `experiment.toml` doesn't set it. See [`retry_wait`](#retry-wait-1).

#### `retryable`

- Type: string (shell command)
- Default: none

The command that decides whether a failed run is retried, for every experiment whose `experiment.toml` doesn't set it. See [`retryable`](#retryable-1).

### `[files]`

#### `path`

- Type: string
- Default: `"{experiment}/files/"`
- Placeholders: `{experiment}`, required, or none for [one experiment](#one-experiment)

Where an experiment's notes and other files live. A glob such as `"{experiment}/*.md"` works too.

### `[runs]`

#### `path`

- Type: string
- Default: `"{experiment}/runs/{run}"`
- Placeholders: `{experiment}` and `{run}`, both required; only `{run}` for [one experiment](#one-experiment)

Where run folders live.

### `[experiment]`

Experiment config kept in `.labnotes.toml`. It takes the same keys as [`experiment.toml`](#experiment-toml), with params under `[experiment.params]`, and is the base that each `experiment.toml` layers over:

- Top-level keys in `experiment.toml` replace the base's.
- `params` merge by name; a param in `experiment.toml` replaces the base's values for that name.
- `env` merges by name; a variable in `experiment.toml` replaces the base's value for that name.
- The merged result is what gets checked, so a key can live in either file, such as `command` in one and `params` in the other.
- `run -e PATH` replaces the `experiment.toml` layer; the base still applies.

```toml
# .labnotes.toml
[experiment]
command = "uv run study.py --output {run_dir}"
continues = false

[experiment.params]
problem = ["2286"]
```

```toml
# experiment.toml
name = "Surprisals"

[params]
max-chars = [70, 80]
```

With no `[experiments] path`, `[experiment]` makes the root [one experiment](#one-experiment), and an `experiment.toml` beside it is optional. To share defaults across many experiments, set `[experiments] path`, such as `"{experiment}"`; experiments without an `experiment.toml` then take the base alone. Project-wide `concurrency`, `retries`, `retry_wait` and `retryable` stay in `[experiments]`.

## `experiment.toml`

One per experiment folder. `labnotes experiments new [NAME]` creates one, optionally from another experiment's with `--from OTHER`; see the [CLI](cli#experiments). `run -e PATH` reads another file in its place.

```toml
name = "Model and effort"
command = "uv run scripts/study.py --output {run_dir}"
meta = "uv run scripts/meta.py"
setup = "docker compose up -d db"
teardown = "docker compose down"
repeats = 5
concurrency = 2
retries = 3
memory_interval = 10
counts = "exit_code = 0 AND created > '2026-10-01'"
continues = true

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]

[env]
PYTHONUNBUFFERED = "1"
OUTPUT_DIR = "{run_dir}"
```

### `command`

- Type: string
- Required

Shell command for one run, run from the project root. Params are appended as flags (see [`[params]`](#params)). The command can write structured output with [`log`](sdk#log).

These placeholders are filled in, each shell-quoted:

- `{run_dir}`: the run folder's absolute path.
- `{invocation_dir}`: the same path as `{run_dir}`. Every retry gets a new `{run_dir}`, unless [`continues`](#continues) is on.

`run.json` records the command with every placeholder filled. [`setup`](#setup), [`teardown`](#teardown), and [`meta`](#meta) get neither placeholder.

### `[env]`

- Type: table of string values
- Default: none

Environment variables for `command`, `meta`, `setup`, and `teardown`. Put shared values under `[experiment.env]` in `.labnotes.toml`; values in `experiment.toml` replace them key by key. Variables already present in the environment that starts `labnotes experiments NAME run`, or that restarts a run from the TUI, take precedence over both, whether exported or supplied inline (`FOO=x labnotes ...`).

Keys must be shell identifiers: letters, digits and underscores, not starting with a digit. The command runs through `sh`, which drops any other name.

Values may use `{run_dir}` and `{invocation_dir}`. They are replaced as raw text, without shell quoting. `setup`, `teardown`, and `meta` get neither placeholder, so a variable whose value uses one is left out of their environment; runs still get it. To pass a value from setup to runs and teardown, use [`set_state`](sdk#set-state-and-get-state).

Names beginning with `LABNOTES_` are reserved for labnotes and cannot be set in the table. The caller's `LABNOTES_*` variables do not override labnotes' own run variables.

### `meta`

- Type: string
- Default: none

Shell command that describes the invocation, such as the git commit it ran. labnotes runs it once when `run` starts, from the project root, before any run starts. Its stdout must be one JSON object:

```toml
meta = "git log -1 --format='{\"commit\":\"%H\"}'"
```

Every run the invocation starts, retries included, gets a copy as `meta` in its `run.json`, written before the run's command starts, so a run that dies early still has it. The `runs` table has it as a `meta` column, so a rule like [`counts`](#counts) can read `meta ->> 'commit'`. Without `meta`, `run.json` has no `meta` key and the column is `NULL`.

A non-zero exit, output that isn't JSON, or JSON that isn't an object fails the invocation before any run starts. The error names the command and shows its stderr. `{run_dir}` or `{invocation_dir}` in the command fails the invocation before `meta` runs.

The command runs once, not per run. A run that waits in the queue keeps the value from the start of the invocation, so if the code changes while it waits, its recorded commit is out of date.

Set it in [`[experiment]`](#experiment) in `.labnotes.toml` to apply it to every experiment.

### `setup`

- Type: string
- Default: none

Shell command that labnotes runs once per `run`, from the project root, after [`meta`](#meta) and before the first run starts. While it runs, the TUI shows `Setting up.`

A non-zero exit fails the invocation: no run starts, but [`teardown`](#teardown) still runs, so it can clean up whatever setup got done before failing. Write teardown to cope with a setup that only got partway. The error names the command and shows its stderr.

Each hook's output is saved in the experiment folder, under `.labnotes/logs/setup/<stamp>/` and `.labnotes/logs/teardown/<stamp>/`. Each folder holds `stdout.log`, `stderr.log`, and `metadata.json` with the command, start and end times, exit code, error, and the run IDs the invocation planned. Setup and teardown from the same invocation share a stamp.

When an experiment has setup or teardown, the TUI shows a row of stages across the top: setup, runs, teardown, each with its state. Setup and teardown each get a screen with their status, elapsed time, and live logs. The TUI opens on setup and moves to the next stage as each one finishes. Press `[` and `]` to move between stages yourself; after that, the TUI stays where you put it.

Setup gets no folder placeholders. `{run_dir}` or `{invocation_dir}` in the command fails the invocation before setup or any run starts. To hand values to runs and teardown, such as a container ID, call [`set_state`](sdk#set-state-and-get-state) in setup; they read it with `get_state`. An [`[env]`](#env) value that uses a placeholder is left out of the hook's environment instead.

`--setup COMMAND` on the command line overrides it. Set it in [`[experiment]`](#experiment) in `.labnotes.toml` to apply it to every experiment; an `experiment.toml` that sets it wins.

Stopping the invocation during setup sends the setup command SIGTERM, the same as a running script, and a second stop kills it. No run starts, and teardown runs once setup has exited.

### `teardown`

- Type: string
- Default: none

Shell command that labnotes runs once per `run`, from the project root, after every run has ended, retries included. It runs whether the runs passed, failed, or were stopped, and even when [`setup`](#setup) failed, the same as a `teardown` export in vitest's `globalSetup`. While it runs, output shows `Tearing down.`

A non-zero exit fails the invocation, with the command and its stderr in the error. The runs' results are already recorded. If setup or the invocation had already failed, that error is the one reported, and the teardown failure is shown as a line of output.

The daemon runs teardown after the last run ends. Leaving or losing the TUI does not stop its runs.

Like `setup`, it gets no folder placeholders and fails before setup if its command uses one. It reads what setup saved with [`get_state`](sdk#set-state-and-get-state).

`--teardown COMMAND` overrides it, and it composes with `.labnotes.toml` the same way as `setup`.

### `name`

- Type: string
- Default: the folder name

Display name, shown in the TUI and the [frontend](../frontend). The folder name stays the key.

### `repeats`

- Type: positive integer
- Default: `1`

Runs per combination of params. `run` plans only the combinations with fewer than `repeats` runs that [count](#counts), so a finished experiment plans nothing. See [Planning Runs](../cli/experiments#planning-runs).

### `[params]`

- Type: table of non-empty lists
- Default: none

Every combination of values runs. Each value is passed as `--name value`, with the name as written. Booleans pass as 0 or 1, lists and tables as JSON. Dates and times are rejected.

Repeating a value weights it: `n = [1, 1, 2]` with `repeats = 1` plans two `n = 1` runs and one `n = 2` run.

Where runs are listed, each param gets a column of its own. A param named like a `runs` column, such as `id` or `command`, or like `started` or `duration`, doesn't: the run's own column keeps the name, labnotes warns once, and the value stays in `params`.

### `concurrency`

- Type: positive integer
- Default: `[experiments] concurrency` in `.labnotes.toml`, else `1`

Runs at once. `--concurrency` on the command line overrides it.

### `retries`

- Type: integer, 0 or more
- Default: `[experiments] retries` in `.labnotes.toml`, else `3`

How many times to retry a run whose command exits 75 (`EX_TEMPFAIL`). Exit 75 means the run failed for a reason outside the experiment, such as no capacity, so labnotes runs it again with the same params. No other exit is retried, unless [`retryable`](#retryable-1) names a command, which then decides for every failed exit. The first retry waits [`retry_wait`](#retry-wait-1) seconds, 30 by default, and each later one waits twice as long. `0` turns retries off.

Each retry gets a new run folder, and its `run.json` holds `"retry_of"` with the id of the run it replaces. The failed run keeps its folder and logs. The default [`counts`](#counts) rule skips it, so a retry doesn't add a repeat. When retries run out, the last run keeps its exit code. Stopping the runs cancels a waiting retry, and a stopped run never retries.

With [`continues`](#continues), a retry runs again in the same folder instead, as another invocation of the same run, and there is no `"retry_of"`.

With `continues`, `retries` also caps how many times a later `run` invokes a failed run again. Every invocation after the first spends one retry, whether it came from a retry or a later `run`, so a run gets at most `retries` + 1 invocations in all. An invocation you stopped (`"ended_by": "stop"`) doesn't count; one that was lost, timed out, or killed by a signal does. Once a run has used them, `run` leaves it alone and doesn't give its combination a new folder, so that combination stays short of `repeats`, and `run` prints `N cells gave up after R retries.` `run --replace-capped` gives such a combination a new run, and `run --run-id ID` invokes the run itself once more.

### `retry_wait`

- Type: number of seconds, 0 or more
- Default: `[experiments] retry_wait` in `.labnotes.toml`, else `30`

How long to wait before the first retry of a failed run. Each later retry waits twice as long as the one before, so `retry_wait = 5` waits 5, 10, then 20 seconds. `--retry-wait` on the command line overrides it.

### `retryable`

- Type: string (shell command)
- Default: `[experiments] retryable` in `.labnotes.toml`, else none

A command that decides whether a failed run is retried. Use it when the exit code alone can't tell: a wrapper may exit 1 both when SSH to a new machine times out, which is worth a retry, and when the code has a bug, which isn't.

```toml
retryable = "uv run retryable.py"
```

After a run exits with a non-zero code, labnotes runs the command from the experiment's folder, with the run's environment, and writes one JSON object to its stdin:

| Key | Value |
|---|---|
| `experiment` | The experiment's name |
| `run` | The run's id |
| `params` | The run's params |
| `command` | The command the run ran |
| `attempt` | 1 for the first attempt, 2 for the first retry, and so on |
| `max_retries` | [`retries`](#retries-1) |
| `created_at`, `started_at`, `finished_at` | ISO 8601 UTC times. With [`continues`](#continues), `started_at` is this invocation's start |
| `duration_s` | Seconds the attempt took |
| `exit_code` | The attempt's exit code |
| `run_folder` | Absolute path to the run folder |
| `stdout`, `stderr` | Absolute paths to this attempt's logs |

Exit 0 retries the run, with the usual [`retry_wait`](#retry-wait-1) backoff, until `retries` runs out. Any other exit, or a command that can't start or crashes, gives up. The command's own output goes to `retryable.log` in the run folder.

Once `retryable` is set it decides for every failed exit, 75 included, so return 0 for 75 too if you still want those retried. A run that didn't start, exited 0, or was stopped never runs it. With no `retryable`, labnotes retries exit 75 only.

```python
import json
import sys
from pathlib import Path

attempt = json.load(sys.stdin)
stderr = Path(attempt["stderr"]).read_text()
sys.exit(0 if attempt["exit_code"] == 75 or "timed out" in stderr else 1)
```

### `memory_interval`

- Type: number of seconds, 0 or more
- Default: `5`

How often to sample a running run's memory. Each sample adds the RSS of the run's process tree and the active memory of its [labeled Docker containers](../cli/experiments#running-experiments), appended as one JSON line to `memory.jsonl` in the run folder and flushed right away:

```json
{"time": 1792800000.5, "rss": 3249999999, "processes": 3}
```

`time` is Unix seconds and `rss` is bytes. Container memory uses the same active-usage calculation as `docker stats` (cgroup usage minus inactive file cache). `processes` counts only processes in the run's host process tree; containers do not increase it. Without Docker, sampling continues with process-tree RSS alone. labnotes keeps every sample, so a run that climbed and was then killed for memory still shows the climb. At 5 seconds a 10-hour run writes about 7,200 lines. `0` turns sampling off and writes no file. Like any key here, it can be set for every experiment in [`[experiment]`](#experiment).

### `[views]`

- Type: table
- Default: none

```toml
[views]
runs = "uv run views/runs.py"
```

`runs` is a shell command, run from the project root, that adds columns to the TUI's runs table. See [Views](views).

### `counts`

- Type: string, a SQL condition over `runs`
- Default: `exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)`

Which runs count toward `repeats`.

### `from`

- Type: string
- Default: none

The experiment this one was copied from. `labnotes experiments new NAME --from OTHER` writes it. labnotes only records it; the copy doesn't follow later changes to OTHER.

### `continues`

- Type: boolean
- Required

Whether `run` invokes a failed run again in its own folder instead of starting a new one. Set it in `experiment.toml` or in [`[experiment]`](#experiment); with neither, `run` fails with a config error. `false` gives a failed run's combination a new folder.

For each combination short of `repeats`, `run` first takes that combination's runs that ended badly (a nonzero exit, stopped, or lost), aren't excluded, don't count, and aren't locked by another `run`. It invokes each of them again in its own folder, with the same params and `{run_dir}`. Any repeats still missing get new folders. labnotes never moves, copies, or deletes the files your command left there, so it can pick up from its own checkpoints.

Each invocation adds an entry to `"invocations"` in `run.json`: `started`, `ended`, `exit_code`, `ended_by`, `error`, `git` (the commit), `dirty`, `patch` (the name of its patch file), `args` (what followed `--`), `labnotes_version`, `labnotes_command`, and the names of its logs. The top-level fields mirror the latest invocation. Each invocation writes its own `stdout-<time>.txt`, `stderr-<time>.txt`, `git-sha-<time>.txt`, and `git-diff-<time>.patch`, so earlier logs and patches are kept.

While an invocation runs, labnotes holds a lock on `run.lock` in the run folder. A run marked running whose lock nobody holds died with its `run`, for example in a reboot. The next look marks it `"ended_by": "lost"`, and the next `run` invokes it again.

A failed run is invoked again at most [`retries`](#retries-1) times.
