"""Exchange one JSON command and one reply with a live daemon."""

import json
import socket

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import socket_record
from labnotes.models import LabnotesConfig


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
