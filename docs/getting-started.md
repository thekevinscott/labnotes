# Getting Started

You can use `labnotes` without installation:

```bash
uvx labnotes
```

Read a bit [about the `labnotes` philosophy](philosophy). You can also read about how to [configure your filesystem](api/config) to work with `labnotes`.

## Config

Assume you have the following structure on disk:

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

You can define a configuration file mapping your files to a SQL layout. `init` will create a config file:

```bash
uvx labnotes init
```

`labnotes` will automatically pick up `.labnotes.toml` when run from the same folder, or specify it with `uvx labnotes -c /path/to/.labnotes.toml`.

*Every key is described in the [config reference](api/config).*

`labnotes` offers the following surfaces:

- a [CLI](cli), for running experiments
- a [frontend](frontend), for analyzing experiments

