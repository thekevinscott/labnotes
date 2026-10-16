**Added** — `labnotes` now serves a local site (default
http://127.0.0.1:8000, change with `--host` / `--port`): a table of
experiments, and a page per experiment showing its fixed and varied
parameters, its rendered markdown notes, completed runs per cell of the
`varies` grid against `runs_per_cell`, and every run with its full record.
Both folders stay watched, so new runs show up on reload.

**Changed** — printing experiments as JSON now needs `--json`, and each entry
carries the design summary and progress counts.
