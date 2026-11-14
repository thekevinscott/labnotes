from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from labnotes.default_counts import DEFAULT_COUNTS
from labnotes.memory_interval import DEFAULT_MEMORY_INTERVAL
from labnotes.retries import DEFAULT_RETRIES, RETRY_SECONDS

Report = Callable[[dict[str, object]], None]


async def no_restart(run: str) -> bool:
    return False


@dataclass(frozen=True)
class Controls:
    interrupt: Callable[[], None]
    set_concurrency: Callable[[int], None]
    kill: Callable[[str], None]
    finish: Callable[[], None]
    finish_up: Callable[[], None]
    start_one: Callable[[str], None]
    restart: Callable[[str], Awaitable[bool]] = no_restart


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
    concurrency: int = 1
    retries: int = DEFAULT_RETRIES
    retry_wait: float = RETRY_SECONDS
    retryable: str | None = None
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
    concurrency: int = 1
    retries: int = DEFAULT_RETRIES
    retry_wait: float = RETRY_SECONDS
    meta: str | None = None
    memory_interval: float = DEFAULT_MEMORY_INTERVAL
    setup: str | None = None
    teardown: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    continues: bool = False
    retryable: str | None = None
    # A run option, not a config key: lets a run that used up `retries` free its slot.
    replace_capped: bool = False
