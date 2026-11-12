"""Probe whether a Unix socket path still has a server behind it."""

import socket
from pathlib import Path


def listening(path: Path) -> bool:
    """Report whether a server accepts connections on the socket path.

    A full backlog makes connect time out, which still means a live server.
    """
    with socket.socket(socket.AF_UNIX) as probe:
        probe.settimeout(1)
        try:
            probe.connect(str(path))
        except TimeoutError:
            return True
        except OSError:
            return False
    return True
