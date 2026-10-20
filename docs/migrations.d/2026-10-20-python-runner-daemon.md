## Summary

Outside a terminal, `labnotes experiments NAME run` now runs through a per-project daemon. The command still blocks until its runs finish and prints the same lines.

## Required changes

| Before | After |
| --- | --- |
| Kill the `run` process to end its runs | `labnotes run stop`, or Ctrl-C / SIGTERM to the `run` process |

Add `.labnotes.sock` to the project's `.gitignore` if it lists files by hand.

## Deprecations removed

None.

## Behavior changes without code changes

- A `.labnotes.sock` socket appears in the project folder while the daemon is up.
- Runs are children of the daemon and share its process group, not one group per run.
- SIGKILL to the waiting `run` process leaves its runs going.
- The daemon exits by itself 15 seconds after nothing is running and no client is connected.

## Verification

```
labnotes experiments NAME run | cat &
ls .labnotes.sock
labnotes run stop    # prints "Stopping runs."
```
