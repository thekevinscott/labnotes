# Common Organizations

`labnotes` reads your folders where they are. Three paths in `.labnotes.toml` tell it where experiments, files and runs live. These are the layouts we see most often. The [config reference](../api/config) covers every key.

## Default

Each experiment is a folder, with its notes in `files` and its runs in `runs`. `uvx labnotes init` writes this one.

<Tree>
data
    experiment-one
        files
            readme.md
        runs/
</Tree>

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

## Notes next to the runs

Notes sit at the top of the experiment folder, and runs go in `results`.

<Tree>
data
    experiment-one
        readme.md
        plan.md
        results/
</Tree>

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/*.md"

[runs]
path = "{experiment}/results/{run}"
```

## Notes and runs in separate trees

Notes live in one tree and data in another, matched by experiment name. This suits notes kept in git with large run outputs kept out of it.

<Tree>
data
    notes
        experiment-one
            readme.md
    runs
        experiment-one/
</Tree>

```toml
[experiments]
path = "notes/{experiment}"

[files]
path = "notes/{experiment}/*.md"

[runs]
path = "runs/{experiment}/{run}"
```

## One experiment per repo

The repo is the experiment: `experiment.toml` sits next to `.labnotes.toml`. labnotes sees that and treats the root as the one experiment, named after its folder. Paths drop `{experiment}`, and `[experiments] path` doesn't apply. With no paths set, notes go in `files/` and runs in `runs/{run}`.

<Tree>
data
    surprisals-experiment
        .labnotes.toml
        experiment.toml
        notes
            plan.md
        runs/
</Tree>

```toml
[files]
path = "notes/"
```

The experiment config can live in `.labnotes.toml` too, under [`[experiment]`](../api/config#experiment); then `experiment.toml` is optional.

Renaming the folder renames the experiment. Runs don't store the name, so nothing on disk changes; only URLs and CLI names do.
