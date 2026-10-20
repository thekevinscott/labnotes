from pathlib import Path

from labnotes.tables.path_pattern import path_pattern

STREAMS = ("stdout", "stderr")


def read_log(root: Path, template: str, path: str) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/{{stream}}.log").fullmatch(relative)
    if found is None or found["stream"] not in STREAMS:
        return []
    return [
        {
            "experiment": found["experiment"],
            "run": found["run"],
            "stream": found["stream"],
            "size": Path(path).stat().st_size,
        }
    ]
