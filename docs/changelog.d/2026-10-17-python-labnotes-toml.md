**Added** — labnotes reads its folders from a `.labnotes.toml` in the working
folder, or the file given with `-c`/`--config`. `experiments` and `data` default to `experiments`
and `data`, resolve relative to the file, and may be absolute or start with
`~`. Flags and `LABNOTES_*` env vars override it. `labnotes context` names the
file and the resolved folders, or says the project has none.
