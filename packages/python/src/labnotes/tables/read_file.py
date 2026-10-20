from pathlib import Path

from labnotes.tables.file_prefix import file_prefix
from labnotes.tables.iso_time import iso_time
from labnotes.tables.path_pattern import path_pattern


def note_text(path: Path) -> str | None:
    if path.suffix != ".md":
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def read_file(root: Path, template: str, path: str) -> list[dict[str, object]]:
    relative = Path(path).relative_to(root).as_posix()
    found = path_pattern(template).fullmatch(relative)
    prefix = path_pattern(file_prefix(template).rstrip("/")).match(relative)
    if found is None or prefix is None:
        return []
    stat = Path(path).stat()
    return [
        {
            "experiment": found["experiment"],
            "filename": relative[prefix.end() :].lstrip("/"),
            "path": relative,
            "ctime": iso_time(stat.st_ctime),
            "mtime": iso_time(stat.st_mtime),
            "mtime_ns": stat.st_mtime_ns,
            "content": note_text(Path(path)),
        }
    ]
