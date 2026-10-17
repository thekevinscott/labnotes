**Added** — `labnotes EXPERIMENT` prints what has run for one experiment as
JSON. `labnotes EXPERIMENT "SQL"` queries that experiment's runs: `runs` is
scoped to its study, `main.runs` holds every run. `labnotes context` prints a
guide for coding agents, and `skills/labnotes` is a skill that points agents
at it (`npx skills add thekevinscott/labnotes`).

**Changed** — `--experiments-folder` and `--data-folder` are now checked by
labnotes instead of click, so `labnotes context` runs without them. A missing
folder still exits `2`.
