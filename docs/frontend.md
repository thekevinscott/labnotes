# Frontend

There's a frontend for interacting with `labnotes`:

```bash
uvx labnotes server
```

Pass `--host` and `--port` as CLI vars and every other uvicorn option.

## Example Organizations

### Default

```
/experiment-one
  /files
    /readme.md
  /runs
```

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/files/"

[runs]
path = "{experiment}/runs/{run}"
```

### Notes next to the runs

```
/experiment-one
  /readme.md
  /plan.md
  /results
```

```toml
[experiments]
path = "{experiment}"

[files]
path = "{experiment}/*.md"

[runs]
path = "{experiment}/results/{run}"
```

### Notes and runs in separate trees

```
/notes
  /experiment-one
    /readme.md
/data
  /experiment-one
```

```toml
[experiments]
path = "notes/{experiment}"

[files]
path = "notes/{experiment}/*.md"

[runs]
path = "data/{experiment}/{run}"
```
