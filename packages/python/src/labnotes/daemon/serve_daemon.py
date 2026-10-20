import asyncio
import contextlib

from labnotes.daemon.run_daemon import run_daemon
from labnotes.models import LabnotesConfig
from labnotes.runner.hold_folder import hold_folder


def serve_daemon(config: LabnotesConfig) -> None:
    lock = contextlib.ExitStack()
    try:
        lock.enter_context(hold_folder(config.root))
    except BlockingIOError:
        return  # Another daemon already serves this project.
    with lock:
        asyncio.run(run_daemon(config))
