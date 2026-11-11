from pathlib import Path

from labnotes.line_index import LineIndex


def log_window(
    indexes: dict[Path, LineIndex], path: Path, first: int, count: int
) -> list[str]:
    index = indexes.get(path)
    if index is None or path.stat().st_size < index.scanned:
        index = indexes[path] = LineIndex(path)
    index.extend()
    return [line.decode("utf-8", "replace") for line in index.read(first, count)]
