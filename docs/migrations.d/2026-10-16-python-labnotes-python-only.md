# labnotes is Python-only

## Summary

The template's Rust CLI and its Python and npm wrappers are replaced by one
pure-Python package, `labnotes`. The crates.io and npm artifacts no longer
exist.

## Required changes

- `pip install mynewproduct` / `npm install mynewproduct` / `cargo add mynewproduct`
  become `uvx labnotes`.
- The `mynewproduct` binary is now `labnotes`.

## Deprecations removed

None.

## Behavior changes without code changes

- Tags are `v{version}`, read by `hatch-vcs`.
- Wheels are pure Python (`py3-none-any`) and need Python 3.12 or later.

## Verification

```sh
uvx labnotes --version
```

Prints the installed version.
