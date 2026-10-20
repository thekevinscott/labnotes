# Getting Started

Run `labnotes` without installing it:

```bash
uvx labnotes
```

## Config

Say your experiments live on disk like this:

```
/data
  /experiment-one
    /files
      /readme.md
      /plan.md
    /runs
  /experiment-two
    /files
      /readme.md
    /runs
```

A `.labnotes.toml` at the root (`/data` here) maps those folders to experiments, files and runs. `init` writes one with the defaults, which match this layout:

```bash
uvx labnotes init
```

`labnotes` picks up `.labnotes.toml` from the folder you run it in. Point it elsewhere with `uvx labnotes -c /path/to/.labnotes.toml`. The [config reference](api/config) covers every key.

## Next

- The [CLI](cli) runs experiments.
- The [frontend](frontend) is for reading and analyzing them.
