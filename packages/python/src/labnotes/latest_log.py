import json
from pathlib import Path


def latest_log(folder: Path, stream: str) -> Path:
    # run.json names each invocation's log; a script's own stdout-*.txt must not win.
    try:
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        run = None
    if isinstance(run, dict):
        match run.get("invocations"):
            case [*_, {**last}] if isinstance(name := last.get(stream), str):
                return folder / Path(name).name
    return folder / f"{stream}.log"
