`labnotes --experiments-folder <dir> --data-folder <dir>` now starts a web
server instead of printing JSON. Add `--json` to keep the old behavior. Each
JSON entry still has `name`, `study`, and `runs`, plus new design and progress
fields.
