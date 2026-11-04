"""Start a detached experiment daemon when no live owner exists."""

import asyncio
import subprocess
import sys

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import discovery_folder
from labnotes.models import LabnotesConfig

START_SECONDS = 10


async def ensure_daemon(config: LabnotesConfig, name: str) -> None:
    """Return once a detached daemon holds the experiment's socket."""
    if daemon_socket(config, name) is not None:
        return
    folder = discovery_folder(config, name)
    folder.mkdir(parents=True, exist_ok=True)
    errors = folder / "daemon.stderr"
    errors.touch(mode=0o600, exist_ok=True)
    with errors.open("ab") as stream:
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
    for _ in range(START_SECONDS * 10):
        if daemon_socket(config, name) is not None:
            return
        if process.poll() is not None:
            detail = errors.read_text().strip()
            raise ValueError(detail or f"Daemon for {name} exited during startup.")
        await asyncio.sleep(0.1)
    raise ValueError(f"Daemon for {name} did not start in {START_SECONDS}s.")
