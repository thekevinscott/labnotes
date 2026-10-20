# TUI

`labnotes experiments NAME run` in a terminal opens a live table of the experiment's runs, with status and time for each. It stays open after the last run finishes. Outside a terminal, `run` prints one line per event instead.

Pending runs show grayed. Running runs spin. Finished runs show `✓`, failed runs a red `✗` with the exit code or error, skipped runs `–` and deselected runs `⊘`. The header shows how many runs go at once.

## Keys

| Key | Action |
| --- | --- |
| `j` / `k` | Move the cursor down / up. |
| `g` / `G` | Jump to the first / last row. |
| `n` | Run the pending run under the cursor next. |
| Space | Deselect a pending run so it won't run. Press again to put it back at the end of the queue. |
| `/` | Filter rows by params text. Enter keeps the filter, Escape clears it. |
| `D` | Deselect every pending run the filter shows. |
| `x` | Stop the running run under the cursor. Press again to kill it. |
| `+` / `-` | Run more / fewer at once. Lowering it lets running runs finish. |
| `f` | Hide or show failed runs. |
| `r` | Run a failed run again under a new id. |
| Enter | Follow the run's `stdout.log` and `stderr.log` as they're written. |
| Escape | Back to the table from a run's output. |
| `q` | Quit. |
| Ctrl-C | Stop every running script and record its end. A second Ctrl-C kills them. |

An `adhoc` run that plans a single run opens straight on its output.

Closing the terminal or sending SIGTERM stops the runs like Ctrl-C, then kills any still going 5 seconds later.
