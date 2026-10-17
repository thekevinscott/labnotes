import posixpath
from pathlib import Path


def lock_path(root: Path, template: str, experiment: str) -> Path:
    head = template.replace("{experiment}", experiment).split("{run}")[0]
    return root / posixpath.dirname(head) / ".labnotes.lock"
