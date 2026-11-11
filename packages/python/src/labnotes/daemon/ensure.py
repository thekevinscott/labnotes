"""Start a detached experiment daemon when no live owner exists."""

import asyncio
import subprocess
import sys
import time

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import discovery_folder
from labnotes.models import LabnotesConfig
from labnotes.tables.iso_time import iso_time


async def ensure_daemon(config: LabnotesConfig, name: str) -> None:
    """Return once a detached daemon holds the experiment's socket."""
    if daemon_socket(config, name) is not None:
        return
    folder = discovery_folder(config, name)
    folder.mkdir(parents=True, exist_ok=True)
    errors = folder / "daemon.stderr"
    errors.touch(mode=0o600, exist_ok=True)
    with errors.open("ab") as stream:
        stream.write(
            f"--- {iso_time(time.time())} starting daemon for {name}\n".encode()
        )
        stream.flush()
        start = stream.tell()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "labnotes",
                "-c",
                str(config.path.resolve()),
                "daemon",
                name,
            ],
            cwd=config.root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=stream,
            start_new_session=True,
        )
    # No deadline: a large project can take long to start, and the caller
    # shows progress. Only the process exiting ends the wait.
    while daemon_socket(config, name) is None:
        if process.poll() is not None:
            # A zero exit lost the lock race; the winner has published by now.
            if daemon_socket(config, name) is not None:
                return
            with errors.open("rb") as log:
                log.seek(start)
                detail = log.read().decode("utf-8", errors="replace").strip()
            raise ValueError(detail or f"Daemon for {name} exited during startup.")
        await asyncio.sleep(0.1)
