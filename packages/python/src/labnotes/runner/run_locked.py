import os
from pathlib import Path

from labnotes.runner.claim_run import claim_run


def run_locked(folder: Path) -> bool:
    lock = claim_run(folder)
    if lock is None:
        return True
    os.close(lock)
    return False
