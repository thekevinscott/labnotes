## Summary

Labnotes now runs experiments in the foreground. The daemon, socket, and attach clients have been removed so each invocation uses the current code and config.

## Required changes

| Before | After |
| --- | --- |
| Start a run in a background shell and attach with `run status` or the Claude Code pane | Start `labnotes experiments NAME run` in a dedicated tmux window and watch it there. |
| `labnotes run stop` or `run control NAME interrupt` | Press Ctrl-C in the run window or close the window. |
| `labnotes run control NAME set_concurrency N` | Use `--concurrency N` when starting or `+`/`-` in the live TUI. |
| `labnotes run status` | Use `labnotes experiments NAME runs --format json` to inspect saved run records. |

## Deprecations removed

The `run status`, `run stop`, and `run control` commands, the hidden `daemon` command, and the Claude Code mod pane are removed.

## Behavior changes without code changes

Closing the terminal or quitting the live TUI stops running commands and records `"ended_by": "stop"` in `run.json`. Runs are not left running for another client to attach. A later invocation finalizes records left unfinished by a dead process.

## Verification

Run `labnotes experiments NAME run` in a tmux window and close it while a run is active. The command exits; `labnotes experiments NAME runs --format json` shows the run with `ended_by` set to `stop`, and no command process remains.
