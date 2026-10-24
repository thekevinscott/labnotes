## Usage

A project that uses labnotes has a `.labnotes.toml` at its root; the folder holding it is the root. labnotes reads it from the working folder, so run labnotes from the project root, or pass `-c PATH`. The lines above this guide name the one found and its paths, or say there is none. `labnotes init` writes one with the default layout:

```toml
[experiments]
path = "{experiment}"            # one folder per experiment

[files]
path = "{experiment}/files/"     # an experiment's notes and other files

[runs]
path = "{experiment}/runs/{run}" # one folder per run
```

Paths are relative to the root. `{experiment}` and `{run}` stand for folder names; the experiments and files paths use `{experiment}`, the runs path both. A project laid out differently keeps its folders and changes the paths: look at where its experiments, notes and runs live, then write the templates that match.

When `experiment.toml` sits next to `.labnotes.toml`, the root is the one experiment, named after its folder. Paths then drop `{experiment}`: files default to `files/`, runs to `runs/{run}`, and `[experiments] path` is rejected. An `[experiment]` table in `.labnotes.toml` holds the same keys as `experiment.toml` and is the base each `experiment.toml` layers over (top-level keys replace, `params` merge by name). With no `[experiments] path`, it also makes the root the one experiment.

`labnotes experiments` reads three tables from those paths:

- `experiments`: `name`, and `config`, the experiment's `experiment.toml` as
  JSON. An experiment is a folder matching the experiments path that holds an
  `experiment.toml`, files or runs.
- `files`: `experiment`, `filename`, `path`, `ctime`, `mtime`.
- `runs`: `experiment`, `id`, `folder`, `created`, `ended`, `exit_code`,
  `error`, `stdout`, `stderr`, `params` as JSON, `meta` as JSON (null without
  a `meta` command), `command`, and `run`, the whole `run.json` as JSON, read
  from each run folder's `run.json`.

Keys come from folder names, so renaming a folder renames its rows on the next
read. Paths are relative to the root, and times are UTC ISO 8601.

```sh
labnotes experiments --format json            # name, last_run, created, files, runs
labnotes experiments foo --format json        # the same, plus config
labnotes experiments foo runs --format json   # foo's runs, oldest first
```

Always pass `--format json` (to parse) or `--format table`. Without `--format`,
all three open an interactive browser when they find a terminal, and wait for
keys that never come.

`labnotes experiments new [NAME]` creates an experiment folder with a starter
`experiment.toml`, picking a random name if you give none. `new` itself can't
be an experiment name.

`labnotes experiments foo run` runs `foo` from its `experiment.toml`, in the
experiments folder:

```toml
name = "Model and effort"
command = "uv run scripts/study.py --output {run_dir}"
repeats = 5

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

`name` is optional: a display name for the experiment, shown in the live view
and as `display_name` in `experiments`. The folder name stays the key, so
renaming the experiment means editing `name`.
Each combination of `[params]` runs `repeats` times (1 if omitted), round-robin, on every
`run`, whatever is already on disk. That is `mode = "adhoc"`, the default.
`mode = "matrix"` counts what is there: only runs that count fill a combination,
so running again fills in what failed or never ran. `mode` under
`[experiments]` in `.labnotes.toml` sets it for every experiment that doesn't
set its own.
Each run gets a new run folder. In `matrix` mode it is named for the UTC time it was planned
(`runs/20261020-000429-brave-fox`). In `adhoc` mode a `run` command that plans one run names
its folder the same way. One that plans more gets one folder named that way, and its runs nest
inside it (`runs/20261020-000429-brave-fox/quiet-river`); the run id is that path under `runs/`. Either way, folder listings sort by start. `command` runs in a shell from the root, with
`{run_dir}` replaced by the run folder's absolute path. Pass it to the
script so it writes its outputs there.
Each param is appended as `--name value`, with the name as written (use
`source-language` for a `--source-language` flag), booleans as 0 or 1, and lists
and tables as JSON. labnotes writes `run.json` (params, `command`, created,
ended, exit code, `ended_by`, `signal`), `stdout.log` and `stderr.log` to the
run folder. `command` is the shell command the run executed, with `{run_dir}`
and the params filled in, written before the run starts, so a killed run has it
and a later edit to `experiment.toml` doesn't hide what a run did. `ended_by` is `"timeout"`, `"stop"` (labnotes stopped it),
`"signal"` (a signal labnotes didn't send, like the out-of-memory killer),
`"lost"` (its process died unseen; the daemon marks these when it starts, with
`ended` set and `exit_code` null) or null (the script exited itself). `signal` is the signal number read from the
exit code (negative, or 128 + N from the shell), else null.
`meta` in `experiment.toml` (or `[experiment]` in `.labnotes.toml`) is a shell
command that prints one JSON object, such as the git commit. labnotes runs it
once from the root when `run` starts and copies it into every run's `run.json`
as `meta`. If it fails or prints anything else, no run starts. Queued runs keep
the value from the start, even if the code changed while they waited.
A run counts when it exited 0 and its `run.json` doesn't hold
`"excluded": true`, so excluding a run by hand means adding that key; the next
`run` replaces it. Other keys you add to `run.json` are kept and show in `run`.
`counts` in `experiment.toml` replaces the rule with a SQL condition over
`runs`, for example `counts = "exit_code = 0 AND created > '2026-10-01'"` to
drop runs from before a script change. The default is
`exit_code = 0 AND NOT coalesce(run ->> 'excluded', false)`.
`experiments foo runs` shows the rule's result as `counted`; queries over
`runs` itself see every run, so apply the rule there too.

A script run by labnotes should:

- take each param as a `--name value` flag, parsing lists and tables from JSON;
- take its output folder as an argument, passed in `command` as `{run_dir}`, and write everything it produces there;
- exit non-zero when it fails, so the run counts as failed and runs again next time;
- exit 75 (`EX_TEMPFAIL`) only when the run couldn't do its work for a reason outside the experiment, like no Docker network or no capacity, so labnotes retries it (see below). labnotes never retries any other exit on its own;
- stop any background process it starts before it exits; the run ends when `command` exits.
- flush its output as it goes (`print(..., flush=True)`, or `PYTHONUNBUFFERED=1`), so the live view shows it as it happens.

A run that exits 75 is retried on its own, with the same params, in a new run
folder whose `run.json` holds `"retry_of": "<run id>"`. The first retry waits 30
seconds, and each one after waits twice as long. `retries` in `experiment.toml`
sets how many (0 turns them off), then `retries` under `[experiments]` in
`.labnotes.toml`, then 2. The failed run keeps its folder, logs and exit code,
and the default `counts` rule skips it, so a retry fills its place rather than
adding a repeat. When the retries run out, the last run keeps exit 75: it never
got to test its params, so treat it as blocked, not as a result. Stopping the
runs, or `x` on a run waiting to retry, cancels the retry. A run that was stopped never retries. The live view
shows a waiting retry as `retry in 30s` and the end as `gave up (exit 75)`;
`run status --json` reports `retrying`, `retried`, `gave up` and
`retry cancelled` events.

Runs can take a long time. Start `run` in the background, then check on it with `labnotes experiments foo runs --format json`; a run with no `ended` is still going. Each run lists `size`, the bytes in its run folder, and a running run lists `memory`, the resident bytes of its command and everything it started.

While a run goes, labnotes appends a memory sample to `memory.jsonl` in its run
folder every 5 seconds: one JSON line, `{"time": <unix seconds>, "rss": <bytes>,
"processes": <count>}`, for the command and everything it started. It keeps
every sample, so a run killed for memory still shows the climb.
`memory_interval` in `experiment.toml` (or `[experiment]` in `.labnotes.toml`)
sets the seconds between samples; 0 turns it off.

In a terminal, `run` shows a live table of runs (status, time, memory and
folder size) and stays
open when they finish. Failed runs show their status in red; `f` hides or shows them, and `r` on one
runs it again under a new id, with `retry_of` set. `j` and `k` move the cursor, `g` and `G` jump to the
first and last row. Runs not started yet show grayed as `pending`, and as
`skipped` once stopped. Move the cursor to a pending run and press `n` to run it
next. `m` grabs a pending run; `j` and `k` move it through the queue, Enter or `m`
drops it, Escape puts it back. Space deselects a pending run so it won't run; Space again puts it back at
the end of the queue. `/` filters rows by params text; Enter keeps the filter,
Escape clears it. `D` deselects every pending run the filter shows. `x` stops the
running run under the cursor; `x` again kills it. `+` and
`-` change how many run at once; lowering it lets running runs
finish. Enter on a run follows its `stdout.log` and `stderr.log` together, as
they're written, and Escape returns to the table. An `adhoc` experiment that
plans a single run opens straight on its output. `q` quits and leaves the runs
going. Elsewhere, it prints a line per event instead.

- `--concurrency N` runs N at a time to start with. Without it, `concurrency`
  in `experiment.toml` sets it, then `concurrency` under `[experiments]` in
  `.labnotes.toml`, then 1.
- `-e PATH` reads another file instead of `experiment.toml`.
- `--timeout SECONDS` stops any one run still going after that many seconds:
  SIGTERM, then SIGKILL 5 seconds later. Its
  `run.json` gets `"error": "timed out after ..."` and `"ended_by": "timeout"`
  next to its exit code.
  Unset, runs have no time limit.
- `run` hands its runs to the project's labnotes daemon, starting it if
  needed, and shows or waits for them. The daemon listens on a socket in
  `/tmp/labnotes-<uid>/` and exits once nothing is running and no client has
  been connected for 15 seconds. Runs belong to the daemon, so quitting the
  live view, closing its terminal, or killing `run` outright leaves them going.
- Ctrl-C stops the running scripts and records their end. A second Ctrl-C
  kills them. SIGTERM stops them the same way, then kills any still going 5
  seconds later. Once the runs are done, either one closes the live view.
- `labnotes run stop` stops every run the daemon has going: SIGTERM, then
  SIGKILL 5 seconds later.
- `labnotes run status` prints what the daemon has going, a line per event so
  far plus the latest line each running run logged and what each running run
  uses (`usage` events with `--json`). `-f` keeps following, and
  waits for a daemon when none is up. `--json` prints one JSON object per line.
  Following doesn't keep the daemon up.
- `labnotes run control NAME ACTION [ARG]` sends one live-view control to a
  running experiment: `kill`, `retry`, `run_next` or `toggle` a run, `move` a
  run to a place in the queue counted from 0,
  `set_concurrency` to a number, `interrupt` or `finish`.
- A second `run` of the same experiment fails while the first is going.
- It exits 0 even if runs fail; the summary line counts failures. A run that
  was retried counts as retried, not failed. If it can't
  start or reach the daemon, it prints the cause on one line and exits 1.

`uvx labnotes server` serves the experiments, their markdown files and their runs as a local site, read from the same `.labnotes.toml`. An experiment's page shows its `experiment.toml` on one line, then a Runs tab with a table of its runs and a Notebooks tab with one tab per markdown file. Clicking a run opens its `stdout.log` and `stderr.log` together, followed as they're written until the run ends.
