from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from labnotes.default_counts import DEFAULT_COUNTS

Report = Callable[[dict[str, object]], None]


@dataclass(frozen=True)
class Controls:
    interrupt: Callable[[], None]
    run_next: Callable[[str], None]
    set_concurrency: Callable[[int], None]
    toggle: Callable[[str], None]


Listen = Callable[[Controls], None]
Start = Callable[[Report, Listen], Coroutine[Any, Any, list[dict[str, object]]]]


@dataclass(frozen=True)
class RunView:
    sort: str | None = None
    descending: bool = False
    status: str | None = None
    filters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LabnotesConfig:
    path: Path
    root: Path
    experiments: str
    files: str
    runs: str


@dataclass(frozen=True)
class ExperimentConfig:
    command: str
    repeats: int
    params: dict[str, list[object]]
    name: str | None = None
    counts: str = DEFAULT_COUNTS
