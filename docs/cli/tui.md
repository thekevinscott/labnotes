# TUI

Running an experiment in a terminal opens the TUI, a live table of the experiment's runs:

```bash
uvx labnotes experiments foo run
```

![The TUI running an experiment](/demos/tui.gif)

From the table you can change how many run at once, stop a run, filter runs by params and read a run's output as it's written. Output does not wrap; scroll sideways to read long lines. The [TUI reference](../api/tui) lists every key.

Experiments with `[views]` also show custom views in the run TUI. Press `1` for the live runs table and `2`–`9` for custom views; `0` returns to the table. The same views and keys are available while browsing.

Runs belong to the experiment's daemon, not the terminal. Press Ctrl-C to quit: `s` stops the runs, Enter or `l` leaves them running, and Escape returns to the table. A TUI crash or lost terminal leaves the daemon running. Run the experiment again to open a new TUI. `run` requires stdout and stderr to be terminals.

A `run` that plans a single run opens straight on its output.

## Browsing

In a terminal, `labnotes experiments` opens a browser instead of printing a table:

```bash
uvx labnotes experiments
uvx labnotes experiments foo
```

The first lists experiments. The second starts on `foo`, and Escape goes back to the list. On an experiment, each run gets a row, including runs that older versions of labnotes nested in one invocation folder. Enter on a run opens its output, which follows the run while it's still writing.

The browser updates as runs start and finish. It only reads; to run an experiment, use `run`.

### Custom views

An experiment can add Textual views to the browse and run TUIs with `[views]` in `experiment.toml`. Press `1` for the built-in runs table and `2`–`9` for custom views in config order. The footer names each view. Press `0` or Escape to return to the runs table; Escape first goes to the current view if it handles that key. Switching views preserves each view's state. See [Views](../api/views) for the config and Python contract.
