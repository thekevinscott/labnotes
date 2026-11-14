import json
from pathlib import Path


def invocation_logs(folder: Path, stream: str) -> list[tuple[str | None, Path]]:
    try:
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        run = None
    invocations = run.get("invocations") if isinstance(run, dict) else None
    logs: list[tuple[str | None, Path]] = []
    for number, invocation in enumerate(
        invocations if isinstance(invocations, list) else [], 1
    ):
        if isinstance(invocation, dict) and isinstance(
            name := invocation.get(stream), str
        ):
            label = f"invocation {number}"
            if isinstance(started := invocation.get("started"), str):
                label += f" · {started}"
            logs.append((label, folder / Path(name).name))
    return logs or [(None, folder / f"{stream}.log")]
