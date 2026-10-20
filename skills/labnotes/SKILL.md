---
name: labnotes
description: Run and inspect experiments with the labnotes CLI - set up an experiment's experiment.toml, run its param grid, check what has run and which runs failed, or answer a question about its runs. Use only when the project has a .labnotes.toml at its root. Do not use to edit notes (edit the files directly).
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

Stop them with `uvx labnotes run stop`.
