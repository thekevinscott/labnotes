## Summary

The run queue can no longer be steered while an experiment runs. The keys and controls for running a run next, moving it, deselecting it, hiding failed runs and retrying by hand are gone from the run TUI, the Claude Code pane and `labnotes run control`. They were rarely used and crowded the footer.

## Required changes

| Before | After |
| --- | --- |
| `labnotes run control NAME run_next RUN` | None. Runs start in planned order. |
| `labnotes run control NAME move RUN PLACE` | None. |
| `labnotes run control NAME toggle RUN` | Narrow the experiment with `--PARAM=VALUE` before running it. |
| `labnotes run control NAME retry RUN` | Run the experiment again. A matrix experiment fills in the missing runs. |

## Deprecations removed

None.

## Behavior changes without code changes

- `labnotes run status --json` and the line-per-event output no longer emit `queued`, `moved`, `deselected` or `reselected`.
- No run shows the `⊘` (deselected) status.
- Runs that exit 75 still retry on their own and still emit `retrying`, `retried`, `gave up` and `retry cancelled`.

## Verification

```
labnotes run control NAME run_next RUN   # Error: ... 'run_next' is not one of 'interrupt', 'set_concurrency', 'kill', 'finish'.
```
