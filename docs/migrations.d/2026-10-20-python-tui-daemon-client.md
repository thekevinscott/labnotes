## Summary

The `labnotes experiments NAME run` live view runs through the project's daemon. Quitting it or closing its terminal no longer ends the runs.

## Required changes

| Before | After |
| --- | --- |
| Close the terminal to end the runs | Ctrl-C in the live view, or `labnotes run stop` |

## Deprecations removed

None.

## Behavior changes without code changes

- `q` quits while runs are going instead of refusing; the runs keep going.
- SIGHUP (closing the terminal) ends the live view only. SIGTERM still stops the runs.
- The runs folder is no longer locked; the daemon refuses a second run of an experiment it is already running.

## Verification

```
labnotes experiments NAME run   # press q while runs are going
labnotes run stop               # prints "Stopping runs."
```
