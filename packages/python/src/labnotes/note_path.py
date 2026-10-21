from pathlib import Path, PurePosixPath

from labnotes.models import LabnotesConfig
from labnotes.tables.file_prefix import file_prefix
from labnotes.tables.path_pattern import path_pattern


def note_path(config: LabnotesConfig, experiment: str, note: str) -> Path | None:
    relative = file_prefix(config.files).replace("{experiment}", experiment) + note
    if ".." in PurePosixPath(relative).parts or not note.endswith(".md"):
        return None
    found = path_pattern(config.files).fullmatch(relative)
    if found is None or (config.experiment or found["experiment"]) != experiment:
        return None
    path = config.root / relative
    return path if path.is_relative_to(config.root) and path.is_file() else None
