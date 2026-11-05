## Summary

Config paths now must resolve inside the project root. Previously a relative path containing `..` or an outward pointing symlink could be accepted and write outside the project.

## Required changes

Change paths that escape the root to paths inside it. For example, change `[runs] path = "../runs-{experiment}/{run}"` to `[runs] path = "runs-{experiment}/{run}"` and move any existing run folders into the new location.

## Deprecations removed

None.

## Behavior changes without code changes

An escaping path now fails config loading with a `path must be relative to the config's folder` error. Existing run folders outside the root are not moved automatically.

## Verification

Run `labnotes experiments` from the project root. It should exit successfully and list experiments when the configured paths resolve inside the root. An escaping path should produce a config error and a nonzero exit.
