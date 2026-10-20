from pathlib import Path

from labnotes.models import LabnotesConfig
from labnotes.tables.file_prefix import file_prefix


def create_note(config: LabnotesConfig, experiment: str) -> str | None:
    def folder(template: str) -> Path:
        return config.root / template.replace("{experiment}", experiment)

    if experiment.startswith(".") or not folder(config.experiments).is_dir():
        return None
    notes = folder(file_prefix(config.files))
    notes.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        filename = f"Untitled {n}.md" if n > 1 else "Untitled.md"
        try:
            with (notes / filename).open("x", encoding="utf-8") as note:
                note.write("# Untitled\n")
            return filename
        except FileExistsError:
            n += 1
