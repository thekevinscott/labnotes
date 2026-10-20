---
diataxis: explanation
---

# Ad hoc runs

<!-- Kevin: draft facts, rewrite in your voice. -->

- The default when no `mode` is set, in `experiment.toml` or under `[experiments]` in `.labnotes.toml`.
- Every `run` plans the full grid: each combination of `[params]`, `repeats` times, whatever is already on disk.
- Each `run` command gets one folder named for the UTC time it was planned, for example `runs/20261020-000429-brave-fox`. Its runs nest inside that folder.
- Nested run folders are named from the params that vary. When nothing varies, a haiku name is used.
- An interrupted run doesn't resume. The next `run` starts a new set.
- The server shows plain counts for an ad hoc experiment. There is no target and no "full" cells.
- When one `run` plans a single run, the live view opens straight into its output.
