from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Experiment:
    """Describe the experiment a view shows.

    `runs` holds one row per run in table order, keyed by run folder relative
    to `root`: the same rows a runs view gets. `groups` holds the invocations,
    their `runs` as those rows, or None when runs aren't nested.
    """

    root: Path
    name: str
    runs: Mapping[str, Mapping[str, Any]]
    columns: tuple[str, ...] = ()
    groups: tuple[Mapping[str, Any], ...] | None = None
    live: bool = False
    runs_view: str | None = None
