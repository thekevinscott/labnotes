## Summary

With `continues = true`, a failed run is now invoked again at most 3 times. It used to be invoked again on every `run`, with no limit.

## Required changes

None, unless you want the old behavior:

| Before | After |
| --- | --- |
| Rely on `continues = true` to invoke a failed run on every `run` | Set `resumes` high in `experiment.toml` or `[experiments]` in `.labnotes.toml`, or pass `run --resumes N`. |

## Deprecations removed

None.

## Behavior changes without code changes

- A run with 4 invocations in `run.json` is left alone. Its combination stays short of `repeats`, and `run` prints `N cells gave up after 3 resumes.`
- `run --replace-capped` gives that combination a new run. `run --run-id ID` still invokes the run itself, whatever its invocations.

## Verification

```
labnotes experiments NAME run
```

On an experiment with a run that has failed 4 times, it prints `1 cell gave up after 3 resumes.` and starts no run for that cell.
