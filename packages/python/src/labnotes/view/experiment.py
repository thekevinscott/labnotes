from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from labnotes.view.group import Group


@dataclass(frozen=True, slots=True)
class Experiment:
    """Describe the experiment a view shows.

    `runs` holds one row per run in run order, keyed by run folder relative to
    `root`: the same rows a runs view gets. `config` is the experiment's config
    as labnotes resolved it. `groups` is None when runs aren't nested.
    """

    root: Path
    name: str
    runs: Mapping[str, Mapping[str, Any]]
    config: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    live: bool = False
    groups: tuple[Group, ...] | None = None
