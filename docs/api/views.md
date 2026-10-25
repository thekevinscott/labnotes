# Views

A runs view adds columns to the [TUI's](tui#browsing) runs table. It is a script you write. labnotes starts it, sends it the table's rows, and draws the columns and rows it sends back.

Views work in the TUI's experiment screen only. The frontend and the CLI ignore them.

## Config

```toml
# experiment.toml
[views]
runs = "uv run views/runs.py"
```

`runs` is a shell command, run from the project root. It can live in `.labnotes.toml` under [`[experiment]`](config#experiment) like any other key, so one script can serve every experiment.

## Writing one

```python
# views/runs.py
from labnotes import view


@view.serve
def runs(columns):
    return [*columns, "model"], lambda row: {**row, "model": row["params"]["model"]}
```

`view.serve` takes a function that gets the table's columns and returns two things: the columns to show, and a function that turns one run's row into the row to show. labnotes calls it once per request, then the row function once per run in the request.

The script reads requests until labnotes closes its stdin. `print` inside it goes to stderr, since stdout carries the answers. `from labnotes import view` loads only the standard library.

`serve` only serves when the decorated function lives in the script labnotes started. Importing the script, say from a test, gives back the plain function:

```python
from views.runs import runs

columns, row = runs([{"key": "id", "label": "id"}])
assert row({"id": "a", "params": {"model": "opus"}})["model"] == "opus"
```

### Example: why a run failed

The reason a run failed is often the last line of its `stderr.log`. This view shows it beside each failed run:

```python
# views/runs.py
from pathlib import Path

from labnotes import view


def last_line(folder):
    path = Path(folder) / "stderr.log"
    text = path.read_text(errors="replace") if path.exists() else ""
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


@view.serve
def runs(columns):
    def row(run):
        failed = run["status"] == "failed"
        return {**run, "reason": last_line(run["folder"]) if failed else ""}

    return [*columns, {"key": "reason", "label": "last stderr"}], row
```

`folder` is relative to the project root, which is where the script runs. When a run's files change, labnotes asks again for that run, so the column fills in as runs fail.

## Columns

A column is an object with a `key` and an optional `label`, or a bare string, which is short for `{"key": name, "label": name}`. Without a `label`, the key is shown. labnotes sends its own columns as objects:

| Key | Label | Shown as |
| --- | --- | --- |
| `status` | (none) | ✓ passed, ✕ failed, ◐ running, – unfinished. |
| `id` | `id` | The run id. |
| `runs` | `runs` | Only when runs are grouped by invocation. Each run's own value is blank. |
| each param that varies | its name | The value. |
| `started` | `started` | `created` in UTC, to the second. |
| `duration` | `duration` | Seconds, as `1m 05s`. |

The answer's columns are the whole table, in order. Leave a column out to hide it; reorder them to move it. labnotes formats every cell after the answer comes back, so `status`, `started` and `duration` keep their look wherever they go. Other values show as text, with lists and objects as JSON.

Columns from a view can't be sorted or filtered.

## Rows

A row is one run, keyed by column. labnotes sends:

| Field | Value |
| --- | --- |
| `experiment`, `id` | The experiment and run id. |
| `folder` | The run folder, relative to the project root. |
| `created`, `ended` | From `run.json`, as written. |
| `exit_code`, `error` | From `run.json`. |
| `stdout`, `stderr` | From `run.json`, when it holds them. |
| `params` | The run's params, as an object. |
| `command` | The shell command the run ran, from `run.json`. |
| `meta` | The run's [`meta`](config#meta), as written to `run.json`, or `null`. |
| `run` | All of `run.json`, as an object. |
| each param that varies | Its value, as in the columns. A param named like another field here keeps that field; read it from `params`. |
| `status` | `"passed"`, `"failed"` or `"unfinished"`. |
| `started` | `created`. |
| `duration` | Seconds from `created` to `ended`, or `null`. |

A row in the answer can keep any field labnotes sent, so `{**row, ...}` works. Any other field must be one of the answer's columns. A column a row leaves out shows blank.

## Protocol

Scripts that don't use Python, or don't want the SDK, can speak the protocol directly. It is newline-delimited JSON (NDJSON): one request per line on the script's stdin, one answer per line on its stdout.

A request:

```json
{"columns": [{"key": "status", "label": ""}, {"key": "id", "label": "id"}], "rows": {"alpha/runs/a": {"id": "a", "folder": "alpha/runs/a", "status": "passed"}}}
```

`rows` is keyed by run folder. An answer has the full column list and a row for each run in the request:

```json
{"columns": [{"key": "status", "label": ""}, {"key": "id", "label": "id"}, "last"], "rows": {"alpha/runs/a": {"id": "a", "last": "done"}}}
```

labnotes sends one request at a time and waits for its answer before the next. The first request holds every run. Later ones hold only the runs whose rows or files changed since the last request, or every run again if labnotes' own columns changed. Runs not in a request keep the rows from their last answer.

An answer is rejected when:

- it isn't one JSON object with `columns` and `rows`;
- a column isn't a string or an object with a string `key`, has a `label` that isn't a string, has any other field, or is listed twice;
- a requested run has no row, or a row is for a run that wasn't requested;
- a row isn't an object, or has a field that is neither a column nor sent by labnotes.

## In the TUI

labnotes starts the command the first time an experiment screen needs it and keeps it for the rest of the session. Experiments with the same command share one process. On quit, labnotes closes the script's stdin, waits a second, then kills it and anything it started.

The line under the table reports problems:

- A rejected answer shows its reason. The table keeps the last good rows, and labnotes keeps sending requests.
- An answer that took over 100 ms shows how long it took. It clears once an answer comes back faster.
- A script that exits shows its last line of stderr.

## Limits

- labnotes asks again only when a file in the run's folder changes. A value that depends on anything else, such as another run or a file outside the folder, goes stale until the run changes.
- A crashed script isn't restarted. Quit and reopen the TUI.
- A script that never answers stops the column from updating. Nothing times it out.
- A change to `[views] runs` takes effect when you reopen the experiment. The old script keeps running until you quit.
