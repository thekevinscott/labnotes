import os
from pathlib import Path

STATE_ENV = "LABNOTES_STATE"


def state_path() -> Path:
    value = os.environ.get(STATE_ENV)
    if not value:
        raise RuntimeError("State is only available in setup and teardown hooks")
    return Path(value)
