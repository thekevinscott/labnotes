import json
from pathlib import Path

from labnotes.tables.path_pattern import path_pattern


def read_memory(
    root: Path, template: str, path: str, experiment: str | None = None
) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/memory.jsonl").fullmatch(relative)
    if found is None:
        return []
    rows: list[dict[str, object]] = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for line, text in enumerate(lines):
        # A run killed mid-write leaves a cut-off last line.
        try:
            sample = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(sample, dict):
            continue
        rows.append(
            {
                "experiment": experiment or found["experiment"],
                "run": found["run"],
                "line": line,
                "time": sample.get("time"),
                "rss": sample.get("rss"),
                "processes": sample.get("processes"),
            }
        )
    return rows
