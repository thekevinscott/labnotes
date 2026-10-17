## Summary

A project now has one root, the folder holding `.labnotes.toml`. The config
names where experiments, their files and their runs live with path templates
instead of two folder keys. `labnotes server` still uses the old two folders
and takes them only from flags or the environment until the site moves to the
new layout.

## Required changes

| Before | After |
| --- | --- |
| `experiments = "experiments"` in `.labnotes.toml` | `[experiments]` `path = "experiments/{experiment}"` |
| `data = "data"` in `.labnotes.toml` | `[runs]` `path = "..."` naming each run folder with `{experiment}` and `{run}` |
| `labnotes server` reading folders from `.labnotes.toml` | `labnotes server --experiments-folder experiments --data-folder data` |

An empty `.labnotes.toml` still works and means the default layout.

## Deprecations removed

None.

## Behavior changes without code changes

A `.labnotes.toml` with `experiments =` or `data =` keys is now an error
(`unknown tables`). `labnotes server` without both folder flags or their
environment variables exits with a usage error.

## Verification

```sh
uvx labnotes init      # writes .labnotes.toml in the working folder
uvx labnotes context   # names the config, its root and its three paths
```
