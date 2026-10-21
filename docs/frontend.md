# Frontend

`labnotes` comes with a local site for reading and analyzing your experiments:

```bash
uvx labnotes server
```

It serves on `http://127.0.0.1:8000`. Pass `--host` and `--port` to change that; every other uvicorn option works too. The [CLI reference](api/cli#server) lists them.

![The experiment page](/screenshots/experiment.png)

Everything on the site reads straight from disk. Edit a file in your editor, or let a script write to a run folder, and the open page updates without a reload.

## Experiments

The home page lists every experiment with its file and run counts, when it was created and when it last ran. Switch between a table and cards with the toggle at the top.

## Runs

An experiment's Runs tab shows a table of its runs, with each param as a column, plus status, start time and duration. Start times show in your browser's time zone.

- Click a column header to sort by it. Click again to reverse.
- Each param column has a filter. Pick the values you want to see, or type to match. Clear filters resets them all.
- Runs still going show as running, with a ticking duration. A run whose script died without recording an end shows as interrupted.
- Click a run to see its `stdout.log` and `stderr.log`. If the run is still going, its output streams in as it's written.

In [`adhoc`](cli/adhoc) mode, runs are grouped by the invocation that made them. Each group row shows its counts and the param values its runs share. Groups start collapsed; while a filter is on, the groups with matches open and show how many of their runs matched.

In [`matrix`](cli/matrix) mode, each combination of params shows its progress toward `repeats`.

The `experiment.toml` button opens the experiment's config.

## Notebooks

The Notebooks tab shows the experiment's markdown files. Click into a note to edit it in place; it saves as you type. The `+` button makes a new note.

Python code blocks in a note run in place. Each note gets its own Python kernel, so later blocks see what earlier ones defined. Restart stops the kernel, and the next run starts a fresh one. Output is saved with the note.

If a note changes on disk while you're editing it, `labnotes` merges the outside changes into your text. When they can't merge, your text stays in the editor and the outside version is saved next to the note as `name (Conflicted copy …).md`, so nothing is lost.
