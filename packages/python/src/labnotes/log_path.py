import os
from pathlib import Path

# The one env contract between runner and script; config is otherwise never env.
LOG_ENV = "LABNOTES_LOG"


def log_path() -> Path | None:
    value = os.environ.get(LOG_ENV)
    return Path(value) if value else None
