**Added** — `labnotes init` writes a `.labnotes.toml` with the default layout,
and refuses to overwrite one.

**Changed** — **BREAKING** ([migration](../migrations.d/2026-10-17-python-config-templates.md)):
`.labnotes.toml` locates experiments, files and runs with path templates under
`[experiments]`, `[files]` and `[runs]`, relative to the folder holding the
config. The `experiments` and `data` keys are gone, and `labnotes server` no
longer reads the config: pass `--experiments-folder` and `--data-folder`.
