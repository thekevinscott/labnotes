**Added** — `-h` and `-p` as short forms of `--host` and `--port`, and
every uvicorn server option (`--reload`, `--workers`, `--proxy-headers`,
`--forwarded-allow-ips`, `--root-path`, `--ssl-*`, `--log-level`, and the
rest) passed straight through. `--experiments-folder` and `--data-folder` also
read `LABNOTES_EXPERIMENTS_FOLDER` and `LABNOTES_DATA_FOLDER`.

**Changed** — uvicorn now logs at its default `info` level, including its
startup line and access log, instead of labnotes printing its own URL line.
`-h` no longer prints help; use `--help`.
