# TUI

Running an experiment in a terminal opens the TUI, a live table of the experiment's runs:

```bash
uvx labnotes experiments foo run
```

![The TUI running an experiment](/demos/tui.gif)

From the table you can choose what runs next, deselect runs you don't want, change how many run at once, stop a run, retry a failed one and read a run's output as it's written. The [TUI reference](../api/tui) lists every key.

Runs belong to the project, not the terminal. Quit the TUI and they keep going; run the experiment again to reopen the table. Outside a terminal, `run` prints a line per event instead, which suits scripts and agents.

An `adhoc` run that plans a single run opens straight on its output.

## Browsing

In a terminal, `labnotes experiments` opens a browser instead of printing a table:

```bash
uvx labnotes experiments
uvx labnotes experiments foo
```

The first lists experiments. The second starts on `foo`, and Escape goes back to the list. On an experiment, runs from one `adhoc` invocation sit under a single row; Enter expands it. Enter on a run opens its output, which follows the run while it's still writing.

The browser updates as runs start and finish. It only reads; to run an experiment, use `run`.
