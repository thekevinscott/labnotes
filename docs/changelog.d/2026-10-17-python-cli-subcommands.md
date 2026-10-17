**Changed** — **BREAKING** ([migration](../migrations.d/2026-10-17-python-cli-subcommands.md)):
labnotes is now a set of subcommands. `labnotes server` serves the site and
takes the folder and uvicorn options; `labnotes context` prints the agent
guide; bare `labnotes` prints the help. `-c`/`--config` goes before the
subcommand.

**Removed** — `--json`, and `labnotes EXPERIMENT ["SQL"]`. A new
`labnotes experiments` command replaces them.
