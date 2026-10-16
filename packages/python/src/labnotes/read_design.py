import json
from pathlib import Path

import yaml


def read_design(path: str) -> list[dict[str, object]]:
    design = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [
        {
            "name": Path(path).parent.name,
            "study": design.get("study"),
            "design": json.dumps(design),
        }
    ]
