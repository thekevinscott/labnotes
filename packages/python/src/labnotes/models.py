from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunView:
    sort: str | None = None
    descending: bool = False
    status: str | None = None
    filters: dict[str, str] = field(default_factory=dict)
