from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from labnotes.daemon.ensure import ensure_daemon
from labnotes.daemon.follow_route import follow_route
from labnotes.models import LabnotesConfig


@dataclass(frozen=True)
class Daemon:
    """Read routes from the experiment's daemon."""

    config: LabnotesConfig
    name: str
    ensure: Callable[[LabnotesConfig, str], Awaitable[None]] = ensure_daemon

    def follow(self, route: str) -> AsyncGenerator[tuple[str, Any], None]:
        """Yield each `(event, data)` the route sends, reconnecting if it drops.

        Raises ValueError when the daemon rejects the route, such as a run or
        file it doesn't know.
        """
        return follow_route(self.config, self.name, route, self.ensure)
