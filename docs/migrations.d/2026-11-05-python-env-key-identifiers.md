## Summary

`[env]` keys must be shell identifiers: letters, digits and underscores, not starting with a digit. Other keys, such as `with-dash`, were silently dropped by `sh` and now fail config loading.

## Required changes

Rename such keys in `experiment.toml` and `[experiment.env]`, for example `with-dash` to `WITH_DASH`, and update the command to read the new name.

## Deprecations removed

None.

## Behavior changes without code changes

A key that is not a shell identifier now fails config loading with an `env.<key> must be a shell identifier` error.

## Verification

Run `labnotes experiments NAME`. It should exit successfully once every `[env]` key is a shell identifier.
