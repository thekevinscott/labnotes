# TUI

`labnotes experiments NAME run` opens the TUI when stdout and stderr are both a terminal. The listing forms open a read-only [browser](#browsing) the same way.

## Statuses

| Glyph | Status |
| --- | --- |
| `○`, grayed | Pending |
| spinner | Running |
| `✓` | Passed |
| `✗`, red | Failed, with the exit code or error |
| `✗ exited 75, retry in 30s`, yellow | Exited 75; retries when the countdown ends |
| `✗ exited 75, retried`, red | Exited 75 and was retried in a new row |
| `✗ gave up (exit 75)`, red | Exited 75 with no retries left |
| `–` | Skipped |
| `⊘` | Deselected |

The header shows the experiment's name and how many runs go at once.

The `memory` column shows how much memory a running run's processes hold: the resident memory of its command and everything it started, summed and sampled each second. The `size` column shows how much its run folder holds on disk. A finished run keeps its size and drops its memory. Both use units of 1000, like `3.2 GB`. Hidden files and folders (names starting with `.`) don't count toward the size. A symlink to a file counts as the size of the file it points to, even when that file lives outside the run folder; symlinked folders aren't followed.

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
| `x` | Stop the running run under the cursor. Press again to kill it. On a run waiting to retry, cancel the retry. |
| `+` / `-` | Run more / fewer at once. Lowering it lets running runs finish. |
| `f` | Hide or show failed runs. |
| `r` | Run a failed run again under a new id. On a run waiting to retry, retry it now. |
| Enter | Open the run's output. |
| Ctrl-p | Open the command palette. |
| Ctrl-C | Quit. With runs going, it asks first. |

## Output keys

The output view follows the run's `stdout.log` and `stderr.log` as they're written. ANSI color and bold show as styled text; other escape codes are dropped. Long lines wrap to the width of the view.

Blocks the script writes with [`log`](sdk#log) show above the raw output, one line each, collapsed and cut off with an ellipsis (▸). Click a block to expand it to its full text (▾); click again to collapse it. A streaming block shows on `start` and grows in place as its deltas arrive. Without a `log.jsonl`, the raw output fills the view as before.

| Key | Action |
| --- | --- |
| Escape | Back to the table. |
| Ctrl-C | Quit, as from the table. |

## Quitting

Ctrl-C with nothing running quits. With runs going, it asks what to do with them:

| Key | Action |
| --- | --- |
| Enter or Ctrl-C | Quit and leave the runs going. |
| `s` | Stop every running script and record its end. Any still going 5 seconds later are killed. |
| Escape | Back to the table. |

So two Ctrl-Cs always quit without losing work. To stop one run, use `x` on its row.

Runs left going belong to the project's daemon, so `run` again reopens the same table, and [`labnotes run status`](cli#run-status) reports on them from any shell.

Closing the terminal leaves the runs going. Sending SIGTERM stops them like `s`.

## Browsing

`labnotes experiments`, `labnotes experiments NAME` and `labnotes experiments NAME runs` open the browser when `--format` is unset and stdout and stderr are both a terminal. Naming an experiment starts on its screen, with the list underneath.

The experiments screen has the same columns as `--format table`. The experiment screen mirrors the runs tab of the [frontend](../frontend): runs from one `adhoc` invocation collapse into one row with pass, fail and running counts; other runs get a row each. Both screens update live and keep the cursor and expanded rows. An experiment removed while open empties its screen with a note in the header.

| Key | Action |
| --- | --- |
| `j` / `k` | Move the cursor down / up. |
| `g` / `G` | Jump to the first / last row. |
| Enter | Open the experiment. On an experiment, expand or collapse an invocation, or open a run's output. |
| Escape | Back. |
| Ctrl-C | Quit. |

A run's output follows its `stdout.log` and `stderr.log` like the run view's, with the run id in the header.
