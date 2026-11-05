# Skill

`labnotes` ships an agent skill, so a coding agent like Claude Code or Codex can drive it for you. Install it with:

```bash
npx skills add thekevinscott/labnotes
```

With the skill installed, the agent can set up an experiment's `experiment.toml`, run its param grid, check what has run and which runs failed, and answer questions about its runs. It only applies in projects with a `.labnotes.toml` at the root. Notes are plain files, so the agent edits them directly.

The skill tells the agent to read `uvx labnotes context` before running anything. That command prints a guide to the CLI for agents, including what a script run by `labnotes` should do. You can read it yourself the same way.

## Running experiments

Start `uvx labnotes experiments NAME run` in a dedicated tmux window. The
TUI shows the live table while a daemon schedules the runs. Closing the
window leaves runs going; Ctrl-C asks whether to stop them or leave them
going. Agents can inspect saved results with
`uvx labnotes experiments NAME runs --format json`.
