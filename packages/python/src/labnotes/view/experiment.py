from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class Experiment:
    """Describe the experiment a view shows.

    `runs` holds one row per run in display order, each with its folder
    relative to `root`. `config` is the experiment's config as labnotes
    resolved it.
    """

    root: Path
    name: str
    runs: Sequence[Mapping[str, Any]]
    config: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
