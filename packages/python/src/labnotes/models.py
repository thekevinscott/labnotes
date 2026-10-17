from dataclasses import dataclass, field
from pathlib import Path


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
