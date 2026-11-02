import fcntl
import os
from pathlib import Path

LOCK_FILE = "run.lock"


def claim_run(folder: Path) -> int | None:
    lock = os.open(folder / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        return None
    return lock
