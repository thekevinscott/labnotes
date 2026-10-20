## Summary

An `experiment.toml` without `mode` now runs ad hoc: each `run` runs every combination `repeats` times again. Before, it filled in only the combinations short of `repeats`. The server shows plain run counts for these experiments, with no target.

## Required changes

| Before | After |
| --- | --- |
| no `mode` (filled the grid) | `mode = "fill"` |

## Deprecations removed

None.
