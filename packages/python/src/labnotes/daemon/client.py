"""Read daemon discovery metadata and exchange one command per connection."""

import fcntl
import json
import os
import socket
from pathlib import Path

from labnotes.daemon.socket_path import lock_path, socket_record
from labnotes.models import LabnotesConfig


def daemon_socket(config: LabnotesConfig, name: str) -> Path | None:
    """Return a socket only while its daemon owns the version-keyed lock."""
    record = socket_record(config, name)
    try:
        path = Path(record.read_text().strip())
    except FileNotFoundError:
        return None
    lock = lock_path(config, name)
    try:
        descriptor = os.open(lock, os.O_RDONLY)
    except FileNotFoundError:
        path.unlink(missing_ok=True)
        record.unlink(missing_ok=True)
        return None
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return path
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    path.unlink(missing_ok=True)
    record.unlink(missing_ok=True)
    return None


def command(
    config: LabnotesConfig, name: str, message: dict[str, object]
) -> dict[str, object]:
    """Send a request and read exactly one reply from the live daemon."""
    path = daemon_socket(config, name)
    if path is None:
        raise ValueError(f"No daemon is running for {name}.")
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(10)
            client.connect(str(path))
            client.sendall((json.dumps(message) + "\n").encode())
            with client.makefile("r") as replies:
                line = replies.readline()
    except OSError as error:
        path.unlink(missing_ok=True)
        socket_record(config, name).unlink(missing_ok=True)
        raise ValueError(f"No daemon is running for {name}.") from error
    if not line:
        raise ValueError(f"Daemon for {name} closed without a reply.")
    reply: dict[str, object] = json.loads(line)
    return reply
