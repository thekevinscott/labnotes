# Philosophy

<!-- Kevin: raw material drawn from your decisions on this project. Rewrite in your voice and cut what doesn't belong. -->

- Local files only. Experiments, notes and runs are plain folders on disk.
- Folders give the data its structure by default. `.labnotes.toml` can overrule that.
- Files are the source of truth. labnotes reads them through dirsql, a read-only SQL view, and writes go straight to disk.
- Generic: it fits any project's layout and isn't built around one.
- An experiment is declared once, in `experiment.toml`. A run uses what's written there, with no extra params from the command line.
- Each run is a folder: `run.json`, `stdout.log`, `stderr.log`, plus whatever the script writes to `{run_dir}`.
- What counts as a finished run is data, a SQL rule in `experiment.toml`, not code.
- Keep it lean: no job queue, no lock files. Add machinery only when a real problem shows up.
- Built for agents as much as people. The skill and `labnotes context` tell an agent how to drive it.
- Trust the user. Don't add defensive guards, and don't shut things down unasked (kernels stay up).
