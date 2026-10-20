from pathlib import Path


def note_text(path: Path) -> str | None:
    if path.suffix != ".md":
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
