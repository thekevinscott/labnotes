from pathlib import Path


def latest_log(folder: Path, stream: str) -> Path:
    # A run that continues writes one log per invocation; follow the newest.
    return max(folder.glob(f"{stream}-*.txt"), default=folder / f"{stream}.log")
