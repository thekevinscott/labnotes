## Summary

`labnotes experiments NAME runs` opens the interactive browser on that experiment when `--format` is unset and stdout and stderr are both terminals. Scripts and agents that run under a pseudo-terminal would wait on it, so they should pass `--format`.

## Required changes

| Before | After |
| --- | --- |
| `labnotes experiments NAME runs` | `labnotes experiments NAME runs --format table` |

## Deprecations removed

None.

## Behavior changes without code changes

Unset `--format` now means the same thing for all three listings: a terminal gets the browser and anything else gets a table.

## Verification

```
labnotes experiments NAME runs --format table   # prints the runs and exits, even in a terminal
labnotes experiments NAME runs | cat            # prints the runs
```
