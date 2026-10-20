import os
from pathlib import Path

from starlette.applications import Starlette

from labnotes.create_app import create_app
from labnotes.read_config import read_config

CONFIG = "LABNOTES_CONFIG"


def serve_app() -> Starlette:
    return create_app(read_config(Path(os.environ[CONFIG])))
