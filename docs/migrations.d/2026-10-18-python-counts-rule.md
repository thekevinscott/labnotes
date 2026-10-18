## Summary

`runs` no longer has `excluded` and `reason` columns. Every `run.json` key is in the new `run` column, and `experiment.toml` can set `counts` to decide which runs count toward `repeats`.

## Required changes

| Before | After |
| --- | --- |
| `SELECT excluded, reason FROM runs` | `SELECT run ->> 'excluded', run ->> 'reason' FROM runs` |
| `excluded` and `reason` in `experiments NAME runs` | `counted`, from the experiment's `counts` rule |

`"excluded": true` in `run.json` still excludes a run under the default rule. An experiment that sets `counts` replaces that rule, so it must check `excluded` itself if it wants hand exclusion.

## Deprecations removed

None.
