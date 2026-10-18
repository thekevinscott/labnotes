import os
from pathlib import Path

from starlette.applications import Starlette

from labnotes.create_app import create_app
from labnotes.read_config import read_config

CONFIG = "LABNOTES_CONFIG"
KERNEL_IDLE_MINUTES = "LABNOTES_KERNEL_IDLE_MINUTES"


def serve_app() -> Starlette:
    return create_app(
        read_config(Path(os.environ[CONFIG])), int(os.environ[KERNEL_IDLE_MINUTES])
    )
