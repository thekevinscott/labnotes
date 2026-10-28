import os
from pathlib import Path

STATE_ENV = "LABNOTES_STATE"
RUN_STATE_ENV = "LABNOTES_RUN_STATE"


def state_path(*, writable: bool = False) -> Path:
    value = os.environ.get(STATE_ENV)
    if not value and not writable:
        value = os.environ.get(RUN_STATE_ENV)
    if not value:
        raise RuntimeError(
            "State is only writable in setup and teardown hooks"
            if writable
            else "State is only available in setup, runs, and teardown"
        )
    return Path(value)
