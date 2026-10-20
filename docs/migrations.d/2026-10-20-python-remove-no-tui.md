## Summary

`labnotes experiments NAME run` no longer takes `--no-tui`. The line-per-event output still appears whenever stdout or stderr isn't a terminal.

## Required changes

| Before | After |
| --- | --- |
| `labnotes experiments NAME run --no-tui` | `labnotes experiments NAME run \| cat` |

## Deprecations removed

None.

## Behavior changes without code changes

None.

## Verification

```
labnotes experiments NAME run | cat   # prints a line per event
```
