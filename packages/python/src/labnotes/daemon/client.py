"""Read the socket record and confirm its daemon owns the lock."""

import fcntl
import operator
import os
from pathlib import Path

from labnotes.daemon.socket_path import lock_path, socket_record
from labnotes.models import LabnotesConfig


def daemon_socket(config: LabnotesConfig, name: str) -> Path | None:
    """Return a socket only while its daemon owns the version-keyed lock."""
    record = socket_record(config, name)
    try:
        path = Path(record.read_text().strip())
    except FileNotFoundError:
        return None
    lock = lock_path(config, name)
    try:
        descriptor = os.open(lock, os.O_RDONLY)
    except FileNotFoundError:
        path.unlink(missing_ok=True)
        record.unlink(missing_ok=True)  # probe
        return None
    try:
        try:
            fcntl.flock(descriptor, operator.or_(fcntl.LOCK_EX, fcntl.LOCK_NB))
        except BlockingIOError:
            return path
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    path.unlink(missing_ok=True)
    record.unlink(missing_ok=True)  # probe
    return None
