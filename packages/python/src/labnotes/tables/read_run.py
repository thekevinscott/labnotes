import json
from pathlib import Path

from labnotes.tables.path_pattern import path_pattern


def read_run(
    root: Path, template: str, path: str, experiment: str | None = None
) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/run.json").fullmatch(relative)
    if found is None:
        return []
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    folder = relative.removesuffix("/run.json")
    return [
        {
            "experiment": experiment or found["experiment"],
            "id": found["run"],
            "folder": folder,
            "created": run.get("created"),
            "ended": run.get("ended"),
            "exit_code": run.get("exit_code"),
            "error": run.get("error"),
            "stdout": f"{folder}/stdout.log",
            "stderr": f"{folder}/stderr.log",
            "params": json.dumps(run.get("params", {})),
            "meta": None if (meta := run.get("meta")) is None else json.dumps(meta),
            "run": json.dumps(run),
        }
    ]
