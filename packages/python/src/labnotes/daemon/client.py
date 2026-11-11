"""Find a live daemon's socket from its record, lock, or listener."""

import fcntl
import operator
import os
import socket
from pathlib import Path

from labnotes.daemon.socket_path import lock_path, socket_path, socket_record
from labnotes.models import LabnotesConfig


def daemon_socket(config: LabnotesConfig, name: str) -> Path | None:
    """Return a socket while its daemon owns the lock or still listens.

    The record and lock live in the state folder, which a user can delete
    under a live daemon; the listener is the last word.
    """
    record = socket_record(config, name)
    try:
        path = Path(record.read_text().strip())
    except FileNotFoundError:
        path = socket_path(config, name)
        return path if listening(path) else None
    if owns_lock(lock_path(config, name)) or listening(path):
        return path
    path.unlink(missing_ok=True)
    record.unlink(missing_ok=True)  # probe
    return None


def owns_lock(lock: Path) -> bool:
    """Report whether some process holds the lock, without waiting for it."""
    try:
        descriptor = os.open(lock, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(descriptor, operator.or_(fcntl.LOCK_EX, fcntl.LOCK_NB))
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def listening(path: Path) -> bool:
    """Report whether a server accepts connections on the socket path."""
    with socket.socket(socket.AF_UNIX) as probe:
        probe.settimeout(1)
        try:
            probe.connect(str(path))
        except TimeoutError:
            return True
        except OSError:
            return False
    return True
