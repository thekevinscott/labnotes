from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Experiment:
    """Describe the experiment a view shows.

    `runs` holds one row per run, keyed by run folder relative to `root`: the
    same rows a runs view gets.
    """

    root: Path
    name: str
    runs: Mapping[str, Mapping[str, Any]]
