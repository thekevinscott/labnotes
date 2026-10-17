**Added** — labnotes reads its folders from a `labnotes.toml` found in the
working folder or a parent. `experiments` and `data` default to `experiments`
and `data`, resolve relative to the file, and may be absolute or start with
`~`. Flags and `LABNOTES_*` env vars override it. `labnotes context` names the
file and the resolved folders, or says the project has none.
