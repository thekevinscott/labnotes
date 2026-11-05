import json
from pathlib import Path


def output_files(folder: Path) -> dict[str, Path] | None:
    try:
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(run, dict):
        return None
    match run.get("invocations"):
        case [*_, dict() as latest]:
            names = latest
        case _:
            names = run
    output = names.get("output")
    if not isinstance(output, str):
        return None
    return {
        "output": folder / output,
        "stdout": folder / str(names.get("stdout", "stdout.log")),
        "stderr": folder / str(names.get("stderr", "stderr.log")),
    }
