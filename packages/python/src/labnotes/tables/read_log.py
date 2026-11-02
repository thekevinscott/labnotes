import re
from pathlib import Path

from labnotes.tables.path_pattern import path_pattern

STREAMS = ("stdout", "stderr")
LOG_NAME = re.compile(r"(?P<stream>[^/.-]+)(?:\.log|-[^/]+\.txt)")


def read_log(
    root: Path, template: str, path: str, experiment: str | None = None
) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(f"{template}/{{log}}").fullmatch(relative)
    name = None if found is None else LOG_NAME.fullmatch(found["log"])
    if found is None or name is None or name["stream"] not in STREAMS:
        return []
    return [
        {
            "experiment": experiment or found["experiment"],
            "run": found["run"],
            "stream": name["stream"],
            "file": found["log"],
            "size": Path(path).stat().st_size,
        }
    ]
