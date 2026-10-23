from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from labnotes.default_counts import DEFAULT_COUNTS
from labnotes.modes import DEFAULT_MODE
from labnotes.retries import DEFAULT_RETRIES

Report = Callable[[dict[str, object]], None]


@dataclass(frozen=True)
class Controls:
    interrupt: Callable[[], None]
    run_next: Callable[[str], None]
    set_concurrency: Callable[[int], None]
    toggle: Callable[[str], None]
    kill: Callable[[str], None]
    retry: Callable[[str], None]
    finish: Callable[[], None]
    move: Callable[[str, int], None]


Listen = Callable[[Controls], None]
Start = Callable[[Report, Listen], Coroutine[Any, Any, list[dict[str, object]]]]


class QueryParams(Protocol):
    def getlist(self, key: str) -> list[str]: ...


@dataclass(frozen=True)
class RunView:
    sort: str | None = None
    descending: bool = False
    status: str | None = None
    filters: dict[str, str] = field(default_factory=dict)
    picked: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class LabnotesConfig:
    path: Path
    root: Path
    experiments: str
    files: str
    runs: str
    mode: str = DEFAULT_MODE
    concurrency: int = 1
    retries: int = DEFAULT_RETRIES
    # Set when the config's folder is itself the one experiment.
    experiment: str | None = None
    # [experiment] in .labnotes.toml, under each experiment.toml.
    defaults: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentConfig:
    command: str
    repeats: int
    params: dict[str, list[object]]
    name: str | None = None
    counts: str = DEFAULT_COUNTS
    mode: str = DEFAULT_MODE
    concurrency: int = 1
    retries: int = DEFAULT_RETRIES
    meta: str | None = None
