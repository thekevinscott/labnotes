from pathlib import Path


def save_note(path: Path, base: str, content: str) -> str | None:
    current = path.read_text(encoding="utf-8")
    if current != base:
        return current
    path.write_text(content, encoding="utf-8")
    return None
