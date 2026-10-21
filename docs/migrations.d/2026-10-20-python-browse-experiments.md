## Summary

`labnotes experiments` and `labnotes experiments NAME` open an interactive browser when `--format` is unset and stdout and stderr are both terminals. Scripts and agents that run under a pseudo-terminal would wait on it, so they should pass `--format`.

## Required changes

| Before | After |
| --- | --- |
| `labnotes experiments` | `labnotes experiments --format table` |
| `labnotes experiments NAME` | `labnotes experiments NAME --format table` |

## Deprecations removed

None.

## Behavior changes without code changes

`--format` has no default. Unset, a terminal gets the browser and anything else gets a table, as before. `labnotes experiments NAME runs` still prints.

## Verification

```
labnotes experiments --format table   # prints the table and exits, even in a terminal
labnotes experiments | cat            # prints the table
```
