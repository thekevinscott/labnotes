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

### Outside labnotes

With `LABNOTES_LOG` unset, as when you run the script yourself, `log` prints `content` to stdout. Blocks without `content`, such as `start` and `stop`, print nothing.
