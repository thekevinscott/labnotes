# Frontend

```sh
uvx labnotes server
```

serves the project's experiments, notes and runs as a local site, read from the same `.labnotes.toml`. It binds to `127.0.0.1:8000`. `--host` and `--port` change that (`--host 0.0.0.0` or a Tailscale IP serves beyond localhost), and every other uvicorn option passes through.

## Index

One row per experiment. An experiment whose `counts` rule doesn't work is flagged in red.

## Experiment page

The experiment's name, then its `experiment.toml` on one line. Click it to see the whole file. A broken `counts` rule shows its error there. Below that are two tabs.

**Runs.** A table of the experiment's runs, with when each started and how long it took. Filters above the columns update as you type. Params with several values get a pick list. In `adhoc` mode, runs from the same `run` command group under a collapsed header row, newest first, showing the group's start, run count and passes and failures. When every `run` made a single run, the table stays flat.

**Notebooks.** One tab per markdown file in the experiment's files folder. `+` adds a note.

- Notes are editable in place and save as you type.
- Edits made outside the browser merge into the open note, with a notice. If a change can't merge, it's saved as `<name> (Conflicted copy YYYYMMDDHHMM).md`.
- A save that started from an old copy of the file is refused, so it can't overwrite newer text.
- Python code blocks have a Run button. Each note gets its own Python kernel, started in the project root, and its outputs stay on the page. Restart starts that kernel fresh. Kernels keep running until you restart them or stop the server.
