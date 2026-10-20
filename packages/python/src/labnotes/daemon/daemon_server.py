from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn


class DaemonServer(uvicorn.Server):
    # A signal stops the runs through the daemon's own handlers; uvicorn's
    # would shut the server down under them.
    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield
