import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from labnotes.models import LabnotesConfig
from labnotes.runner.runs_parent import runs_parent


@contextmanager
def hold_experiment(config: LabnotesConfig, name: str) -> Iterator[None]:
    folder = runs_parent(config.root, config.runs, name)
    made = not folder.exists()
    folder.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                f"{name} is already running in another labnotes run."
                " Wait for it to finish, or stop it, then run again."
            ) from None
        yield
    finally:
        if made:
            with suppress(OSError):
                folder.rmdir()
        os.close(descriptor)
