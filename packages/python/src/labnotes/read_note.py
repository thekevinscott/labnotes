from pathlib import Path


def read_note(path: str) -> list[dict[str, object]]:
    note = Path(path)
    return [
        {
            "experiment": note.parent.name,
            "name": note.name,
            "content": note.read_text(encoding="utf-8"),
        }
    ]
