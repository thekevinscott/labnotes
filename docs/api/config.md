# Config

labnotes reads two kinds of TOML file: one `.labnotes.toml` per project, and one `experiment.toml` per experiment. Unknown tables, unknown keys and invalid TOML are errors.

## `.labnotes.toml`

Must be at the project root; the folder holding it is the root. labnotes reads it from the working folder, or from `-c PATH`. `labnotes init` writes one with the defaults below and refuses to overwrite an existing file.

```toml
[experiments]
path = "{experiment}"
mode = "adhoc"
concurrency = 1
retries = 2

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

Paths are relative to the root. Absolute paths and `~` are rejected.

### One experiment

When `experiment.toml` sits next to `.labnotes.toml`, or `.labnotes.toml` has an [`[experiment]`](#experiment) table and no `[experiments] path`, the root is the project's one experiment. Its name is the root folder's name; `name` in `experiment.toml` stays the display name. Paths can't use `{experiment}` and `[experiments] path` is rejected; `mode`, `concurrency`, and `retries` still apply. The defaults become:

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

#### `mode`

- Type: `"adhoc"` | `"matrix"`
- Default: `"adhoc"`

Mode for every experiment whose `experiment.toml` doesn't set one. See [`mode`](#mode-1).

#### `concurrency`

- Type: positive integer
- Default: `1`

Runs at once for every experiment whose `experiment.toml` doesn't set it.

#### `retries`

- Type: integer, 0 or more
- Default: `2`

Retries for a run that exits 75, for every experiment whose `experiment.toml` doesn't set it. See [`retries`](#retries-1).

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
- The merged result is what gets checked, so a key can live in either file, such as `command` in one and `params` in the other.
- `run -e PATH` replaces the `experiment.toml` layer; the base still applies.

```toml
# .labnotes.toml
[experiment]
command = "uv run study.py --output {run_dir}"

[experiment.params]
problem = ["2286"]
```

```toml
# experiment.toml
name = "Surprisals"

[params]
max-chars = [70, 80]
```

With no `[experiments] path`, `[experiment]` makes the root [one experiment](#one-experiment), and an `experiment.toml` beside it is optional. To share defaults across many experiments, set `[experiments] path`, such as `"{experiment}"`; experiments without an `experiment.toml` then take the base alone. Project-wide `mode`, `concurrency`, and `retries` stay in `[experiments]`.

## `experiment.toml`

One per experiment folder. `labnotes experiments new [NAME]` creates one. `run -e PATH` reads another file in its place.

```toml
name = "Model and effort"
command = "uv run scripts/study.py --output {run_dir}"
meta = "uv run scripts/meta.py"
repeats = 5
mode = "matrix"
concurrency = 2
retries = 3
memory_interval = 10
counts = "exit_code = 0 AND created > '2026-10-01'"

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

### `command`

- Type: string
- Required

Shell command for one run, run from the project root. `{run_dir}` becomes the run folder's absolute path, shell-quoted. Params are appended as flags (see [`[params]`](#params)). The command can write structured output with [`log`](sdk#log).

### `meta`

- Type: string
- Default: none

Shell command that describes the invocation, such as the git commit it ran. labnotes runs it once when `run` starts, from the project root, before any run starts. Its stdout must be one JSON object:

```toml
meta = "git log -1 --format='{\"commit\":\"%H\"}'"
```

Every run the invocation starts, retries included, gets a copy as `meta` in its `run.json`, written before the run's command starts, so a run that dies early still has it. The `runs` table has it as a `meta` column, so a rule like [`counts`](#counts) can read `meta ->> 'commit'`. Without `meta`, `run.json` has no `meta` key and the column is `NULL`.

A non-zero exit, output that isn't JSON, or JSON that isn't an object fails the invocation before any run starts. The error names the command and shows its stderr.

The command runs once, not per run. A run that waits in the queue keeps the value from the start of the invocation, so if the code changes while it waits, its recorded commit is out of date.

Set it in [`[experiment]`](#experiment) in `.labnotes.toml` to apply it to every experiment.

### `name`

- Type: string
- Default: the folder name

Display name, shown in the TUI and as `display_name` in `labnotes experiments`. The folder name stays the key.

### `repeats`

- Type: positive integer
- Default: `1`

Runs per combination of params.

### `[params]`

- Type: table of non-empty lists
- Default: none

Every combination of values runs. Each value is passed as `--name value`, with the name as written. Booleans pass as 0 or 1, lists and tables as JSON. Dates and times are rejected.

### `mode`

- Type: `"adhoc"` | `"matrix"`
- Default: `[experiments] mode` in `.labnotes.toml`, else `"adhoc"`

`"adhoc"`: every `run` plans the full grid. A single run writes one flat folder; several nest inside one new folder. `"matrix"`: `run` plans only the combinations with fewer than `repeats` counted runs, in flat run folders.

### `concurrency`

- Type: positive integer
- Default: `[experiments] concurrency` in `.labnotes.toml`, else `1`

Runs at once. `--concurrency` on the command line overrides it.

### `retries`

- Type: integer, 0 or more
- Default: `[experiments] retries` in `.labnotes.toml`, else `2`

How many times to retry a run whose command exits 75 (`EX_TEMPFAIL`). Exit 75 means the run failed for a reason outside the experiment, such as no capacity, so labnotes runs it again with the same params. No other exit is retried. The first retry waits 30 seconds and each later one waits twice as long. `0` turns retries off.

Each retry gets a new run folder, and its `run.json` holds `"retry_of"` with the id of the run it replaces. The failed run keeps its folder and logs. The default [`counts`](#counts) rule skips it, so a retry doesn't add a repeat. When retries run out, the last run keeps exit 75. Stopping the runs cancels a waiting retry, and a stopped run never retries.

### `memory_interval`

- Type: number of seconds, 0 or more
- Default: `5`

How often to sample a running run's memory. Each sample is the resident memory of the run's command and everything it started, appended as one JSON line to `memory.jsonl` in the run folder and flushed right away:

```json
{"time": 1792800000.5, "rss": 3249999999, "processes": 3}
```

`time` is Unix seconds, `rss` is bytes, and `processes` is how many processes it counted. labnotes keeps every sample, so a run that climbed and was then killed for memory still shows the climb. At 5 seconds a 10-hour run writes about 7,200 lines. `0` turns sampling off and writes no file. Like any key here, it can be set for every experiment in [`[experiment]`](#experiment).

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

Which runs count toward `repeats`. `labnotes experiments NAME runs --format table` shows the result as `counted`.
