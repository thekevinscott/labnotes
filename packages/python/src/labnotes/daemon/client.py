"""Find a live daemon's socket from its record, lock, or listener."""

import fcntl
import operator
import os
from pathlib import Path

from labnotes.daemon.listening import listening
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
    try:
        descriptor = os.open(lock_path(config, name), os.O_RDONLY)
    except FileNotFoundError:
        descriptor = None
    if descriptor is not None:
        try:
            try:
                fcntl.flock(descriptor, operator.or_(fcntl.LOCK_EX, fcntl.LOCK_NB))
            except BlockingIOError:
                return path
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
    if listening(path):
        return path
    path.unlink(missing_ok=True)
    record.unlink(missing_ok=True)
    return None
