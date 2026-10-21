## Summary

`q` said "Quit" but left the runs going, while Ctrl-C stopped them, and the labels didn't say which. Both TUIs now quit on Ctrl-C only. In the run TUI, Ctrl-C with runs going asks whether to leave them running or stop them, and leaving them is the default.

## Required changes

| Before | After |
| --- | --- |
| `q` to quit either TUI | Ctrl-C |
| Ctrl-C in the run TUI to stop the runs | Ctrl-C, then `s` |
| A second Ctrl-C to kill them | `s` kills any still going 5 seconds later; `x` twice kills one run |

## Deprecations removed

None.

## Behavior changes without code changes

- Two Ctrl-Cs in the run TUI leave the runs going instead of stopping and killing them.
- Ctrl-C with nothing running quits at once.
- SIGTERM still stops the runs, then kills any still going 5 seconds later.

## Verification

```
labnotes experiments NAME run   # press Ctrl-C while runs are going
                                # shows "N runs still going. Leave them running (enter) / stop them (s) / cancel (esc)."
```
