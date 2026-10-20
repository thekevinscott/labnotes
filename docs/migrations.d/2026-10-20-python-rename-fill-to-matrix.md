## Summary

The `fill` mode is renamed `matrix`.

## Required changes

| Before | After |
| --- | --- |
| `mode = "fill"` in `experiment.toml` | `mode = "matrix"` |
| `mode = "fill"` under `[experiments]` in `.labnotes.toml` | `mode = "matrix"` |

## Deprecations removed

None.

## Behavior changes without code changes

None. A `matrix` experiment plans and counts runs exactly as `fill` did.

## Verification

```
labnotes experiments NAME run   # errors with "mode must be matrix or adhoc" if "fill" is left
```
