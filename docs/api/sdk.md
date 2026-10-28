# SDK

Scripts that labnotes runs can import from the `labnotes` package. Install it in the script's environment, for example with `uv add labnotes`.

## `log`

```python
from labnotes import log

log({"content": "final answer"})
```

`log` writes one structured block of output for the current run. Use it for output that is too much to read as raw stdout, such as a model's thinking or its tool calls. Each call takes a dict.

`from labnotes import log` loads only the standard library, so it adds nothing heavy to a script.

### Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `content` | string | The block's text. |
| `id` | string | Ties the phases of a streaming block together. |
| `phase` | `"start"` \| `"delta"` \| `"stop"` | Where a streaming block is. Leave it out for a complete block. |
| `type` | string | Free label, such as `"thinking"`. labnotes doesn't use it yet. |
| `timestamp` | string | Added by labnotes when the block is written, in UTC with milliseconds. A `timestamp` passed in is replaced. |

Blocks are flat. A block can't hold other blocks.

### Complete blocks

A block without `phase` is complete:

```python
log({"type": "answer", "content": "42"})
```

### Streaming blocks

Text that arrives in pieces is one block written in phases. `start` opens it, each `delta` adds a piece of `content`, and `stop` closes it. The same `id` ties them together:

```python
log({"id": "t1", "phase": "start", "type": "thinking"})
for chunk in stream:
    log({"id": "t1", "phase": "delta", "content": chunk})
log({"id": "t1", "phase": "stop"})
```

A block with no `stop`, say from a crashed run, stays open.

### Where blocks go

When labnotes [runs a script](../cli/experiments#running-experiments), it sets `LABNOTES_LOG` in the script's environment to `log.jsonl` in the run folder. `log` appends one JSON line per call to that file, next to `stdout.log` and `stderr.log`:

```json
{"id": "t1", "phase": "delta", "content": "chunk", "timestamp": "2026-10-21T09:15:02.481Z"}
```

Each run gets its own `LABNOTES_LOG`. labnotes replaces any value the script inherits from outside, so a script started by another run still logs to its own run folder.

labnotes also sets `LABNOTES_RUN` to the absolute run folder path, replacing any inherited value. Scripts can use it to [label Docker containers](../cli/experiments#running-experiments) so their memory is counted with the run. The path distinguishes runs across experiments and projects on the machine.

### Outside labnotes

With `LABNOTES_LOG` unset, as when you run the script yourself, `log` prints `content` to stdout. Blocks without `content`, such as `start` and `stop`, print nothing.

## `set_state` and `get_state`

Use state to pass resource IDs or connection details from [setup](config#setup) to run commands and [teardown](config#teardown):

```python
# setup.py
from labnotes import set_state

set_state({"container": "abc123"})
set_state({"port": 8000})
```

```python
# run.py or teardown.py
from labnotes import get_state

state = get_state()  # {"container": "abc123", "port": 8000}
```

`set_state(values: dict[str, object]) -> None` merges by top-level key. A repeated key replaces its entire value; other keys survive. Values must be JSON serializable. `get_state() -> dict[str, object]` returns the saved state, or `{}` if setup has not written any. Teardown may follow a failed setup, so it should handle missing keys.

Run commands can call `get_state()` after setup finishes. Every run, including queued runs and retries, reads the same invocation state file. `set_state()` raises `RuntimeError` in runs: only setup and teardown can write, so parallel runs cannot overwrite each other's state or change what teardown receives.

Both functions use only the standard library and raise `RuntimeError` outside an invocation and in `meta`. They take no invocation IDs.

Labnotes sets `LABNOTES_STATE` for setup and teardown to `state.json` in `{invocation_dir}`, and `LABNOTES_RUN_STATE` for run commands to the same file. That file stays in the invocation folder. When several matrix runs have no shared folder, labnotes uses a temporary file that remains available through all runs and teardown and is removed afterward, including when a hook fails. `meta` receives neither state variable; state is not copied into `run.json`.

When a hook or run starts another labnotes invocation, the inner invocation clears inherited `LABNOTES_*` context for its children, then sets its own hook state and run variables. Its SDK calls cannot bind to the outer invocation through those inherited values.

## `view`

```python
from labnotes import view


@view.serve
def runs(columns):
    return [*columns, "model"], lambda row: {**row, "model": row["params"]["model"]}
```

`view.serve` turns a script into a [runs view](views), which adds columns to the TUI's runs table. Like `log`, it loads only the standard library.
