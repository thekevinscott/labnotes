# TUI

`labnotes experiments NAME run` opens the TUI when stdout and stderr are both a terminal.

## Statuses

| Glyph | Status |
| --- | --- |
| `○`, grayed | Pending |
| spinner | Running |
| `✓` | Passed |
| `✗`, red | Failed, with the exit code or error |
| `–` | Skipped |
| `⊘` | Deselected |

The header shows the experiment's name and how many runs go at once.

## Table keys

| Key | Action |
| --- | --- |
| `j` / `k` | Move the cursor down / up. |
| `g` / `G` | Jump to the first / last row. |
| `n` | Run the pending run under the cursor next. |
| `m` | Grab the pending run under the cursor. `j` / `k` move it through the queue, Enter or `m` drops it, Escape puts it back. |
| Space | Deselect a pending run so it won't run. Press again to put it back at the end of the queue. |
| `/` | Filter rows by params text. Enter keeps the filter, Escape clears it. |
| `D` | Deselect every pending run the filter shows. |
| `x` | Stop the running run under the cursor. Press again to kill it. |
| `+` / `-` | Run more / fewer at once. Lowering it lets running runs finish. |
| `f` | Hide or show failed runs. |
| `r` | Run a failed run again under a new id. |
| Enter | Open the run's output. |
| `q` | Quit. |
| Ctrl-p | Open the command palette. |
| Ctrl-C | Stop every running script and record its end. A second Ctrl-C kills them. |

## Output keys

The output view follows the run's `stdout.log` and `stderr.log` as they're written.

| Key | Action |
| --- | --- |
| Escape | Back to the table. |
| `q` | Quit. |

## Quitting

Quitting the TUI leaves the runs going. They belong to the project's daemon, so `run` again reopens the same table, and [`labnotes run status`](cli#run-status) reports on them from any shell.

Closing the terminal or sending SIGTERM stops the runs like Ctrl-C, then kills any still going 5 seconds later.
