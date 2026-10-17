## Summary

labnotes moved from one command to subcommands, so the coming `init`,
`experiments` and `run` commands have somewhere to live. Serving moved to
`labnotes server`. The JSON dump and the per-experiment query were removed; a
new `labnotes experiments` command replaces them.

## Required changes

| Before | After |
| --- | --- |
| `labnotes [--experiments-folder X --data-folder Y] [uvicorn options]` | `labnotes server [--experiments-folder X --data-folder Y] [uvicorn options]` |
| `labnotes -c path.toml ...` | `labnotes -c path.toml server ...` |
| `labnotes --json` | none yet; use `labnotes server`, or query the data folder with `uvx dirsql -c data/.dirsql.toml "SQL"` |
| `labnotes EXPERIMENT ["SQL"]` | none yet; same as above |

## Deprecations removed

None.

## Behavior changes without code changes

Bare `labnotes` prints the help and exits 0 instead of serving.

## Verification

```sh
uvx labnotes --help        # lists context and server
uvx labnotes server --help # lists --experiments-folder, --data-folder and the uvicorn options
```
