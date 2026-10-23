# Common Organizations

`labnotes` reads your folders where they are. Three paths in `.labnotes.toml` tell it where experiments, files and runs live. These are the two layouts we see most often. The [config reference](../api/config) covers every key.

## One Folder, One Experiment

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

## One Run Tree, Many Experiments

Notes stay with each experiment, and all runs go in one `runs` tree with a folder per experiment. labnotes still groups the runs by experiment.

<Tree>
data
    experiments
        experiment-one
            files
                readme.md
    runs
        experiment-one/
</Tree>

```toml
[experiments]
path = "experiments/{experiment}"

[files]
path = "experiments/{experiment}/files/"

[runs]
path = "runs/{experiment}/{run}"
```

Pick this one when runs are large and synced as one unit. `runs/` can be a single Hugging Face dataset, git clone or rsync target. With the first layout, each experiment's runs sit in their own folder, so syncing them means one dataset or remote per experiment, with history split across them. A new experiment here is a new folder in the same tree, not a new remote.
