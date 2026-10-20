---
diataxis: explanation
---

# Fill runs

<!-- Kevin: draft facts, rewrite in your voice. -->

- Set `mode = "fill"` in `experiment.toml`, or under `[experiments]` in `.labnotes.toml` for every experiment. The experiment's own setting wins.
- A combination of `[params]` is full once it has `repeats` runs that count. `run` plans only what is missing, so running again fills in what failed or never ran.
- By default a run counts when it exited 0 and its `run.json` doesn't hold `"excluded": true`.
- `counts` in `experiment.toml` replaces that rule with a SQL condition over `runs`, for example `exit_code = 0 AND created > '2026-10-01'`.
- Excluded and failed runs don't count toward `repeats`.
- Run folders are flat: `runs/20261020-000429-brave-fox`, named for the UTC time they were planned.
- The server shows progress toward `repeats` for each combination.
