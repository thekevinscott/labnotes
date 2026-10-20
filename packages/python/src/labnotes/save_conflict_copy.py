from datetime import datetime
from itertools import chain, count
from pathlib import Path


def save_conflict_copy(path: Path, content: str, now: datetime) -> Path:
    stamp = f"Conflicted copy {now:%Y%m%d%H%M}"
    tags = chain([stamp], (f"{stamp} {n}" for n in count(2)))
    while True:
        copy = path.with_name(f"{path.stem} ({next(tags)}){path.suffix}")
        try:
            with copy.open("x", encoding="utf-8") as file:
                file.write(content)
            return copy
        except FileExistsError:
            pass
