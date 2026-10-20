# Common Organizations

`labnotes` reads your folders where they are. Three paths in `.labnotes.toml` tell it where experiments, files and runs live. These are the layouts we see most often. The [config reference](api/config) covers every key.

## Default

Each experiment is a folder, with its notes in `files` and its runs in `runs`. `uvx labnotes init` writes this one.

<Tree>
data
    experiment-one
        files
            readme.md
        runs
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
        results
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
        experiment-one
</Tree>

```toml
[experiments]
path = "notes/{experiment}"

[files]
path = "notes/{experiment}/*.md"

[runs]
path = "runs/{experiment}/{run}"
```
