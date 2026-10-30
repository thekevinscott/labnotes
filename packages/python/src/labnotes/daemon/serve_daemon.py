import asyncio
import contextlib

from labnotes.daemon.run_daemon import run_daemon
from labnotes.daemon.socket_path import socket_path
from labnotes.models import LabnotesConfig
from labnotes.runner.hold_folder import hold_folder


def serve_daemon(config: LabnotesConfig) -> None:
    # Labnotes 0.0.136 and older lock the project folder itself.
    path = socket_path(config.root).with_suffix(".lock")
    path.touch()
    lock = contextlib.ExitStack()
    try:
        lock.enter_context(hold_folder(path))
    except BlockingIOError:
        return  # Another daemon of this version already serves this project.
    with lock:
        asyncio.run(run_daemon(config))
