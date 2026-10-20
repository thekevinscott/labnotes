## Summary

Ad hoc runs nest under a folder per `run` command, and `run.json` drops `invocation_id`.

## Required changes

| Before | After |
| --- | --- |
| `run ->> 'invocation_id'` groups runs from one command | the run id's first segment (the parent folder) |
| ad hoc run id `20261020-000429-brave-fox` | `20261020-000429-brave-fox/quiet-river` |

## Deprecations removed

None.
