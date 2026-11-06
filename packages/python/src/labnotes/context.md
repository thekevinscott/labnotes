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

When `experiment.toml` sits next to `.labnotes.toml`, the root is the one experiment, named after its folder. Paths then drop `{experiment}`: files default to `files/`, runs to `runs/{run}`, and `[experiments] path` is rejected. An `[experiment]` table in `.labnotes.toml` holds the same keys as `experiment.toml` and is the base each `experiment.toml` layers over (top-level keys replace, `params` and `env` merge by name). With no `[experiments] path`, it also makes the root the one experiment.

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
be an experiment name. `--command`, `--param NAME=VALUE` (repeat it for several
values) and `--repeats` write those settings into the file. `--from OTHER`
copies another experiment's `experiment.toml` and files, never its runs, and
records `from = "OTHER"`; the other flags replace the copied values.

`labnotes experiments foo run` runs `foo` from its `experiment.toml`, in the
experiments folder:

```toml
name = "Model and effort"
command = "uv run scripts/study.py --output {run_dir}"
repeats = 5
continues = false

[params]
model = ["opus", "sonnet"]
effort = ["low", "high"]
```

`name` is optional: a display name for the experiment, shown in the live view
and as `display_name` in `experiments`. The folder name stays the key, so
renaming the experiment means editing `name`.
Each combination of `[params]` needs `repeats` runs that count (1 if omitted).
`run` plans only the combinations short of that, round-robin, so running again
fills in what failed or never ran, and a finished experiment plans nothing
(`Nothing to run: every combination has its repeats.`). To start over, copy it
with `experiments new NAME --from OLD`, which drops `mode` and fills in
`continues`. `mode` is gone; setting it is a config error.
`continues` is required, in `experiment.toml` or `[experiment]` in
`.labnotes.toml`. `continues = true` invokes a failed, stopped or lost run again
in its own folder, with the same params and `{run_dir}`; `run.json` then lists
each attempt under `"invocations"`. `continues = false` gives the combination a
new folder. Never delete `run.json`, `stdout-*`, `stderr-*` or `run.lock` from a
run folder.
Each new run gets a run folder named for the UTC time it was planned
(`runs/20261020-000429-brave-fox`), so folder listings sort by start. Older
versions nested several runs in one invocation folder
(`runs/20261020-000429-brave-fox/quiet-river`, run id is that path); those still
list and count. Only one `run` of an experiment goes at a time; a second refuses. `command` runs in a shell from the root, with
`{run_dir}` replaced by the run folder's absolute path. Pass it to the
script so it writes its outputs there. `{invocation_dir}` is the same
folder as `{run_dir}`. Both placeholders are shell-quoted.
Each param is appended as `--name value`, with the name as written (use
`source-language` for a `--source-language` flag), booleans as 0 or 1, and lists
and tables as JSON. labnotes writes `run.json` (params, `command`, created,
ended, exit code, `ended_by`, `signal`, `git`), `stdout.log` and `stderr.log` to the
run folder. `command` is the shell command the run executed, with the placeholders
and the params filled in, written before the run starts, so a killed run has it
and a later edit to `experiment.toml` doesn't hide what a run did. `ended_by` is `"timeout"`, `"stop"` (labnotes stopped it),
`"signal"` (a signal labnotes didn't send, like the out-of-memory killer),
`"lost"` (its process died unseen; the next run marks these when it starts, with
`ended` set and `exit_code` null) or null (the script exited itself). `signal` is the signal number read from the
exit code (negative, or 128 + N from the shell), else null.
`git` is `{"commit": "<full HEAD SHA>", "dirty": false}`, read from the command's
working directory before each run starts, including retries. `dirty` counts staged
and unstaged changes to tracked files only, ignoring untracked files. `git` is
null outside a Git repository, if Git is missing, or if lookup fails (including
a repository with no commits). Older records lack the key.
`meta` in `experiment.toml` (or `[experiment]` in `.labnotes.toml`) is a shell
command that prints one JSON object, such as the git commit. labnotes runs it
once from the root when `run` starts and copies it into every run's `run.json`
as `meta`. If it fails or prints anything else, no run starts. Queued runs keep
the value from the start, even if the code changed while they waited.
`setup` and `teardown` (same places; `--setup`/`--teardown` override) are shell
commands run once per `run` from the root: setup before the first run starts,
teardown after the last one ends, even if runs failed, were stopped, or setup
failed (so teardown must cope with a partial setup). A failing setup starts no
run; a failing teardown fails the invocation. Hooks and `meta` get no folder
placeholders: `{run_dir}` or `{invocation_dir}` in one fails before anything
starts. Share values through state instead.
Setup can call `labnotes.set_state({"container": "abc"})`; runs and teardown read the
dict with `labnotes.get_state()`. Writes merge by top-level key, replacing an
existing value without dropping other keys. Values must be JSON serializable;
reading before any write returns `{}`. Runs can only read: `set_state` raises
`RuntimeError` there. Both functions raise outside an invocation and in `meta`.
Labnotes gives setup/teardown `LABNOTES_STATE` and runs `LABNOTES_RUN_STATE`,
pointing to a temp file kept through all runs and teardown and then removed. Queued runs and retries
read the same file after setup finishes. `meta` receives neither state variable;
state is never copied into `run.json`.
Nested labnotes invocations clear inherited `LABNOTES_*` context for their
children and set their own hook and run variables.
`[env]` in `experiment.toml` sets string environment values for `command`,
`meta`, `setup`, and `teardown`. `[experiment.env]` in `.labnotes.toml`
provides shared values; experiment values replace them by name. Variables in
the environment that starts `labnotes experiments NAME run` win over both,
including inline assignments. Values can use raw `{run_dir}` and
`{invocation_dir}` placeholders. Hooks and meta get neither, so values using
one are left out of their environment; runs still get them.
`LABNOTES_*` names are reserved for labnotes.
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
The live view reports `retrying`, `retried`, `gave up` and
`retry cancelled` events.

Runs can take a long time. Start `run` in a dedicated tmux window, then check on it with `labnotes experiments foo runs --format json`; a run with no `ended` is still going. Each run lists `size`, the bytes in its run folder, and a running run lists `memory`, the resident bytes of its command and everything it started.

While a run goes, labnotes appends a memory sample to `memory.jsonl` in its run
folder every 5 seconds: one JSON line, `{"time": <unix seconds>, "rss": <bytes>,
"processes": <count>}`, for the command's process tree and its labeled Docker
containers. `LABNOTES_RUN` is the absolute run folder path; scripts label containers
with `docker run --label "labnotes.run=$LABNOTES_RUN" ...` to count their memory.
`processes` counts host processes in the run's tree, not containers. It keeps
every sample, so a run killed for memory still shows the climb.
`memory_interval` in `experiment.toml` (or `[experiment]` in `.labnotes.toml`)
sets the seconds between samples; 0 turns it off.

In a terminal, `run` shows a live table of runs (status, time, memory and
folder size) and stays
open when they finish. Failed runs show their status in red. `j` and `k` move the cursor, `g` and `G` jump to the
first and last row. Runs not started yet show grayed as `pending`, and as
`skipped` once stopped. `/` filters rows by params text; Enter keeps the filter,
Escape clears it. `x` stops the
running run under the cursor; `x` again kills it. `+` and
`-` change how many run at once; lowering it lets running runs
finish. Enter on a run follows its `stdout.log` and `stderr.log` together, as
they're written, and Escape returns to the table. A `run` that
plans a single run opens straight on its output. `q` quits and leaves the runs
going. `run` requires a terminal.

- `--concurrency N` runs N at a time to start with. Without it, `concurrency`
  in `experiment.toml` sets it, then `concurrency` under `[experiments]` in
  `.labnotes.toml`, then 1.
- `-e PATH` reads another file instead of `experiment.toml`.
- `--PARAM=VALUE` runs only the cells where that param has that value, e.g.
  `labnotes experiments NAME run --model=small`. PARAM must be a key in
  `[params]` and VALUE one of its values, written as it shows in `runs`
  (`true`, `2`); anything else is an error. Repeat a param to run any of
  several values (`--model=small --model=large`); give several params to
  narrow further (`--model=small --lang=en`). Values are never split on
  commas. It changes only what
  this `run` starts: counts, progress and `repeats` still cover the full
  matrix, so a later plain `run` fills in the rest. Use it instead of editing
  `experiment.toml` to run a slice.
- `--timeout SECONDS` stops any one run still going after that many seconds:
  SIGTERM, then SIGKILL 5 seconds later. Its
  `run.json` gets `"error": "timed out after ..."` and `"ended_by": "timeout"`
  next to its exit code.
  Unset, runs have no time limit.
- `run` requires a terminal and opens the live table. The experiment daemon
  owns the runs and starts the next planned run when a concurrency slot is free.
  Agents should start the TUI in a dedicated tmux window.
- Ctrl-C opens a prompt while setup, runs, retries, or teardown are pending:
  `s` stops the experiment like `stop`, Enter or `l` leaves it running and
  prints the stop command, and Escape returns to the table. Once it is done,
  Ctrl-C quits at once. Closing the terminal leaves runs going.
  Stopped runs receive SIGTERM, then SIGKILL after 5 seconds if needed.
- A second invocation starts its own run session and reads the current config.
- The TUI summary counts passed, failed and retried runs. If `run` cannot
  start, it prints the cause and exits nonzero. Without a terminal it exits 2.

`uvx labnotes server` serves the experiments, their markdown files and their runs as a local site, read from the same `.labnotes.toml`. An experiment's page shows its `experiment.toml` on one line, then a Runs tab with a table of its runs and a Notebooks tab with one tab per markdown file. The Runs tab also has a grid (`?view=grid`): one cell per combination of the params that vary, with how many runs count toward `repeats`. Clicking a run opens its `stdout.log` and `stderr.log` together, followed as they're written until the run ends.
