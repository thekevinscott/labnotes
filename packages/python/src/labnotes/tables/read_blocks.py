from pathlib import Path

from labnotes.tables.path_pattern import path_pattern


def read_blocks(
    root: Path, template: str, path: str, experiment: str | None = None
) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/log.jsonl").fullmatch(relative)
    if found is None:
        return []
    return [
        {
            "experiment": experiment or found["experiment"],
            "run": found["run"],
            "size": Path(path).stat().st_size,
        }
    ]
