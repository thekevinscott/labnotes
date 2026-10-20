## Summary

`labnotes experiments NAME run` exits 0 once its runs finish, even if some failed. It still exits non-zero when it can't start, such as when the experiment is missing or locked.

## Required changes

| Before | After |
| --- | --- |
| exit code 1 means a run failed | read the `N passed, M failed.` line, or each run's `exit_code` in `run.json` |

## Deprecations removed

None.

## Behavior changes without code changes

Scripts that checked `run`'s exit code for failed runs now see 0.

## Verification

```
labnotes experiments NAME run; echo $status   # 0, even with failed runs
```
