from datetime import datetime
from pathlib import Path


def save_conflict_copy(path: Path, content: str, now: datetime) -> Path:
    stamp = f"Conflicted copy {now:%Y%m%d%H%M}"
    n = 1
    while True:
        tag = stamp if n == 1 else f"{stamp} {n}"
        copy = path.with_name(f"{path.stem} ({tag}){path.suffix}")
        try:
            with copy.open("x", encoding="utf-8") as file:
                file.write(content)
            return copy
        except FileExistsError:
            n += 1
