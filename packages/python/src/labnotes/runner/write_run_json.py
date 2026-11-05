import json
import os
from pathlib import Path


def write_run_json(folder: Path, run: dict[str, object]) -> None:
    partial = folder / f"run.json.{os.getpid()}.tmp"
    partial.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    partial.replace(folder / "run.json")
