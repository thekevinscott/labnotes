import os
from pathlib import Path

LOG_ENV = "LABNOTES_LOG"
RUN_ENV = "LABNOTES_RUN"


def log_path() -> Path | None:
    value = os.environ.get(LOG_ENV)
    return Path(value) if value else None
