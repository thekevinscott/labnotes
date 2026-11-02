# TUI

Running an experiment in a terminal opens the TUI, a live table of the experiment's runs:

```bash
uvx labnotes experiments foo run
```

![The TUI running an experiment](/demos/tui.gif)

From the table you can change how many run at once, stop a run, filter runs by params and read a run's output as it's written. The [TUI reference](../api/tui) lists every key.

Runs belong to the project, not the terminal. Press Ctrl-C to quit and the TUI asks whether to leave them going or stop them; run the experiment again to reopen the table. Outside a terminal, `run` prints a line per event instead, which suits scripts and agents.

A `run` that plans a single run opens straight on its output.

## Browsing

In a terminal, `labnotes experiments` opens a browser instead of printing a table:

```bash
uvx labnotes experiments
uvx labnotes experiments foo
```

The first lists experiments. The second starts on `foo`, and Escape goes back to the list. On an experiment, runs that older versions of labnotes nested in one invocation folder sit under a single row, marked ▸; Enter expands it (▾). Enter on a run opens its output, which follows the run while it's still writing.

The browser updates as runs start and finish. It only reads; to run an experiment, use `run`.

### Custom views

An experiment can add Textual views to the browser with `[views]` in `experiment.toml`. Press `1` for the built-in runs table and `2`–`9` for custom views in config order. The footer names each view. Press `0` or Escape to return to the runs table; Escape first goes to the current view if it handles that key. Switching views preserves each view's state. See [Views](../api/views) for the config and Python contract.
