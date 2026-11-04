## Summary

With `continues = true`, a failed run used to be invoked again on every `run`, with no limit. Now `retries` caps it, counting retries after exit 75 too. The `retries` default goes from 2 to 3.

## Required changes

None, unless you want the old behavior:

| Before | After |
| --- | --- |
| Rely on `continues = true` to invoke a failed run on every `run` | Set `retries` high in `experiment.toml` or `[experiments]` in `.labnotes.toml`, or pass `run --retries N`. |
| Rely on the default of 2 retries after exit 75 | Set `retries = 2`. |

## Deprecations removed

None.

## Behavior changes without code changes

- With `continues = true`, a run with 4 invocations in `run.json` is left alone. Its combination stays short of `repeats`, and `run` prints `1 cell gave up after 3 retries.`
- With `continues = true`, `retries = 0` now also means a failed run is never invoked again. Raise it if you set it only to turn off exit-75 retries.
- A run that exits 75 now gets 3 retries, not 2. With `continues = true`, a resumed run only gets the retries its earlier invocations left.
- `run --replace-capped` gives an out-of-retries combination a new run. `run --run-id ID` still invokes the run itself, whatever its invocations.

## Verification

```
labnotes experiments NAME run
```

On an experiment with `continues = true` and a run that has failed 4 times, it prints `1 cell gave up after 3 retries.` and starts no run for that cell.
