---
name: labnotes
description: Run and inspect experiments with the labnotes CLI - set up an experiment's experiment.toml, run its param grid, change concurrency or stop runs that are going, check what has run and which runs failed, or answer a question about its runs. Use only when the project has a .labnotes.toml at its root. Do not use to edit notes (edit the files directly).
allowed-tools: Bash(uvx labnotes:*), Bash(labnotes:*)
---

# labnotes

Learn how to use `labnotes` before running it:

```bash
uvx labnotes context
```

Start runs from a background shell command, so you hear when they finish
without holding the conversation. Without a terminal, `run` blocks until its
runs end and prints a line per event:

```bash
uvx labnotes experiments NAME run
```

Always pass `--format json` (or `--format table`) to `labnotes experiments`.
Without it, a terminal gets an interactive browser that waits for keys.

Stop them with `uvx labnotes run stop`. Check on them with
`uvx labnotes run status`. Change them while they run with
`uvx labnotes run control NAME ACTION [ARG]`, e.g.
`uvx labnotes run control NAME set_concurrency 5`. Don't talk to the daemon's
socket directly; its location is internal.
