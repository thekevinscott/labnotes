# Skill

`labnotes` ships an agent skill, so a coding agent like Claude Code or Codex can drive it for you. Install it with:

```bash
npx skills add thekevinscott/labnotes
```

With the skill installed, the agent can set up an experiment's `experiment.toml`, run its param grid, check what has run and which runs failed, and answer questions about its runs. It only applies in projects with a `.labnotes.toml` at the root. Notes are plain files, so the agent edits them directly.

The skill tells the agent to read `uvx labnotes context` before running anything. That command prints a guide to the CLI for agents, including what a script run by `labnotes` should do. You can read it yourself the same way.

## Mods

In Claude Code, the skill also installs mods that bring the run table into the session.

The agent starts runs in a background shell, so the conversation isn't held while they go. It opens a pane with the same live table as the [TUI](cli/tui) through its `show_runs` tool, after starting runs or when you ask to watch them. You can also open the pane yourself with `/labnotes-runs`. It opens at once, even mid-turn, and costs no model turn. Click the pane to use its keys. The [TUI keys](api/tui) work there, except the pane never sees Escape or Ctrl-C: `q` goes back from a run's output or puts a moved run back, and `X` stops all runs.

A run's output in the pane shows the blocks its script logs with [`labnotes.log`](api/sdk#log) above its stdout and stderr, as the TUI does. Each block is one line, cut off at the pane's edge. Click a block to read all of it, and click again to fold it. A streaming block grows in place as its pieces arrive.

When a run finishes or fails, a toast says so, whether or not the pane is open.

The pane and the terminal are both views of the project's daemon, so you can watch the same runs in either.
