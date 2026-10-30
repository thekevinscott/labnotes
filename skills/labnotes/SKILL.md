---
name: labnotes
description: Run and inspect experiments with the labnotes CLI - set up an experiment's experiment.toml, run its param grid, change concurrency in the live view or stop runs that are going, check what has run and which runs failed, or answer a question about its runs. Use only when the project has a .labnotes.toml at its root. Do not use to edit notes (edit the files directly).
allowed-tools: Bash(uvx labnotes:*), Bash(labnotes:*)
---

# labnotes

Learn how to use `labnotes` before running it:

```bash
uvx labnotes context
```

Start runs in a dedicated tmux window. Keep the labnotes process in the
foreground there so it can schedule the next run as a slot frees. Closing the
window stops its runs cleanly. Without a terminal, `run` blocks until all runs
end and prints a line per event:

```bash
uvx labnotes experiments NAME run
```

To run part of the grid, name params on the command line instead of editing
`experiment.toml`. This runs only the cells where `model` is `small`:

```bash
uvx labnotes experiments NAME run --model=small
```

Each flag must name a param in `[params]` and one of its values. Several flags
narrow further. The experiment's totals still count the full grid.

Always pass `--format json` (or `--format table`) to `labnotes experiments`.
Without it, a terminal gets an interactive browser that waits for keys.

Watch runs in the tmux window. Stop them with Ctrl-C there, or close the
window. To inspect saved runs from another shell, use
`uvx labnotes experiments NAME runs --format json`.
