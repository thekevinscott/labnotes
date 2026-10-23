from pathlib import Path

from labnotes.tables.path_pattern import path_pattern


def read_run_file(
    root: Path, template: str, path: str, experiment: str | None = None
) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/**").fullmatch(relative)
    if found is None:
        return []
    stat = Path(path).stat()
    return [
        {
            "experiment": experiment or found["experiment"],
            "path": relative,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    ]
