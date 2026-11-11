# TUI

`labnotes experiments NAME run` requires stdout and stderr to be terminals and opens the TUI. The listing forms open a read-only [browser](#browsing) the same way.

Each table numbers its rows from 1 down the left edge. The numbers follow the rows shown, so a filter renumbers them.

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

The header shows the experiment's name and how many runs go at once.

The `memory` column shows how much memory a running run's processes hold: the resident memory of its command and everything it started, summed and sampled each second. The `size` column shows how much its run folder holds on disk. A finished run keeps its size and drops its memory. Both use units of 1000, like `3.2 GB`. Hidden files and folders (names starting with `.`) don't count toward the size. A symlink to a file counts as the size of the file it points to, even when that file lives outside the run folder; symlinked folders aren't followed.

## Table keys

| Key | Action |
| --- | --- |
| `j` / `k` | Move the cursor down / up. |
| `g` / `G` | Jump to the first / last row. |
| `/` | Filter rows by params text. Enter keeps the filter, Escape clears it. |
| `x` | Stop the running run under the cursor. Press again to kill it. On a run waiting to retry, cancel the retry. |
| `f` | Finish up: drop queued runs and pending retries. Running runs finish normally; the TUI stays open. |
| `+` / `-` | Run more / fewer at once. Lowering it lets running runs finish. |
| Enter | Open the run's output. |
| Ctrl-p | Open the command palette. |
| Ctrl-C | Quit. While the experiment is still busy, it asks first. |

## Output keys

The output view follows the run's `stdout.log` and `stderr.log` as they're written, each in its own tab. A tab's label counts its complete lines, such as `stdout (33)` and `stderr (5)`, and updates while the run writes. The view opens on stdout. For a run that [continues](config#continues), it follows the latest invocation's logs. ANSI color and bold show as styled text; other escape codes are dropped. Long lines wrap. While you're scrolled to the bottom, the view follows new output; scroll up to read back, and scroll to the bottom again to follow. The view reads only the lines on screen, so a log of any size opens fast and uses little memory. Scrolling moves one log line at a time, however many rows it wraps to. A line longer than 64 KB shows its first 64 KB.

Blocks the script writes with [`log`](sdk#log) show above the raw output, one line each, collapsed and cut off with an ellipsis (▸). Click a block to expand it to its full text (▾); click again to collapse it. A streaming block shows on `start` and grows in place as its deltas arrive. Without a `log.jsonl`, the raw output fills the view as before.

| Key | Action |
| --- | --- |
| `t` | Switch between the stdout and stderr tabs. Clicking a tab works too. |
| `f` | Finish up: drop queued runs and pending retries while continuing to watch this run. |
| Escape | Back to the table. |
| Ctrl-C | Quit, as from the table. |

## Quitting

Ctrl-C quits at once only when the experiment is done. While it is setting up, running, waiting to retry, or tearing down, it asks first, and the prompt says which:

| Key | Action |
| --- | --- |
| Enter or `l` | Quit and leave the experiment going. The TUI prints the `labnotes experiments NAME attach` and `labnotes experiments NAME stop` commands as it exits. |
| `s` | Stop the experiment, the same as `labnotes experiments NAME stop`. No more runs start, running scripts are stopped and any still going 5 seconds later are killed, and teardown still runs. A setup hook that has begun finishes first. |
| Escape | Back to the table. |

To stop one run, use `x` on its row.

The daemon owns the runs. Quitting the TUI can stop or leave them running.

Closing the terminal leaves the runs going.

## Browsing

`labnotes experiments`, `labnotes experiments NAME` and `labnotes experiments NAME runs` open the browser when `--format` is unset and stdout and stderr are both a terminal. Naming an experiment starts on its screen, with the list underneath.

The experiments screen has the same columns as `--format table`. The experiment screen lists every run as its own row. Unlike the [frontend](../frontend), it doesn't group runs that older versions of labnotes nested in one invocation folder; their id shows that folder. Both screens update live and keep the cursor. An experiment removed while open empties its screen with a note in the header. A [runs view](views) adds columns to the experiment screen, and a line under the table reports when it fails or answers slowly.

| Key | Action |
| --- | --- |
| `j` / `k` | Move the cursor down / up. |
| `g` / `G` | Jump to the first / last row. |
| Enter | Open the experiment. On an experiment, open a run's output. |
| Escape | Back. |
| Ctrl-C | Quit. |

A run's output follows its `stdout.log` and `stderr.log` like the run view's, with the run id in the header.
