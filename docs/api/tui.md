# TUI

`labnotes experiments NAME run` opens the TUI when stdout and stderr are both a terminal. The listing forms open a read-only [browser](#browsing) the same way.

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
| `m` | Grab the pending run under the cursor. `j` / `k` (or the arrow keys) move it through the queue, Enter or `m` drops it, Escape puts it back. |
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

The output view follows the run's `stdout.log` and `stderr.log` as they're written. ANSI color and bold show as styled text; other escape codes are dropped.

Blocks the script writes with [`log`](sdk#log) show above the raw output, one line each, collapsed and cut off with an ellipsis (▸). Click a block to expand it to its full text (▾); click again to collapse it. A streaming block shows on `start` and grows in place as its deltas arrive. Without a `log.jsonl`, the raw output fills the view as before.

| Key | Action |
| --- | --- |
| Escape | Back to the table. |
| `q` | Quit. |

## Quitting

Quitting the TUI leaves the runs going. They belong to the project's daemon, so `run` again reopens the same table, and [`labnotes run status`](cli#run-status) reports on them from any shell.

Closing the terminal or sending SIGTERM stops the runs like Ctrl-C, then kills any still going 5 seconds later.

## Browsing

`labnotes experiments`, `labnotes experiments NAME` and `labnotes experiments NAME runs` open the browser when `--format` is unset and stdout and stderr are both a terminal. Naming an experiment starts on its screen, with the list underneath.

The experiments screen has the same columns as `--format table`. The experiment screen mirrors the runs tab of the [frontend](../frontend): runs from one `adhoc` invocation collapse into one row with pass, fail and running counts; other runs get a row each. Both screens update live and keep the cursor and expanded rows. An experiment removed while open empties its screen with a note in the header.

| Key | Action |
| --- | --- |
| `j` / `k` | Move the cursor down / up. |
| `g` / `G` | Jump to the first / last row. |
| Enter | Open the experiment. On an experiment, expand or collapse an invocation, or open a run's output. |
| Escape | Back. |
| `q` | Quit. |

A run's output follows its `stdout.log` and `stderr.log` like the run view's, with the run id in the header.
