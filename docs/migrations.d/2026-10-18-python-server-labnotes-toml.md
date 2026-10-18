## Summary

`labnotes server` reads the project's `.labnotes.toml`, like `experiments` and `run`. The folder options and the `design.yaml` and data-folder `.dirsql.toml` files are no longer read.

## Required changes

| Before | After |
| --- | --- |
| `labnotes server --experiments-folder X --data-folder Y` | `labnotes server` from the project root, or `labnotes -c PATH server` |
| `LABNOTES_EXPERIMENTS_FOLDER`, `LABNOTES_DATA_FOLDER` | none; the config path picks the project |
| `design.yaml` with `varies` and `runs_per_cell` | `experiment.toml` with `[params]` and `repeats` |
| `design.yaml` `study`, matched against a `study` column | none; runs belong to the experiment whose runs path holds them |
| `design.yaml` `completed_run` | none; a run counts when it exited 0 and isn't excluded |
| `design.yaml` `fixed` | a param with one value |
| notes as `*.md` in the experiment folder | `*.md` files under the files path (`{experiment}/files/` by default) |

## Deprecations removed

None.

## Behavior changes without code changes

Python blocks in notes run with the project root as their working folder instead of the data folder. The runs table lists newest first by `created`.

## Verification

```sh
uvx labnotes server --help # no --experiments-folder or --data-folder
uvx labnotes server        # from a folder with .labnotes.toml
```
