import os
from pathlib import Path

from starlette.applications import Starlette

from labnotes.create_app import create_app

EXPERIMENTS_FOLDER = "LABNOTES_EXPERIMENTS_FOLDER"
DATA_FOLDER = "LABNOTES_DATA_FOLDER"


def serve_app() -> Starlette:
    return create_app(
        Path(os.environ[EXPERIMENTS_FOLDER]), Path(os.environ[DATA_FOLDER])
    )
