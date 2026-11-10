"""Exchange one JSON command and one reply with a live daemon."""

import json
import socket

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import socket_record
from labnotes.models import LabnotesConfig

CONNECT_TIMEOUT_SECONDS = 10
# The server allows 30 seconds for start preparation; leave room for its reply.
START_REPLY_TIMEOUT_SECONDS = 40


def command(
    config: LabnotesConfig, name: str, message: dict[str, object]
) -> dict[str, object]:
    """Send a request and read exactly one reply from the live daemon."""
    path = daemon_socket(config, name)
    if path is None:
        raise ValueError(f"No daemon is running for {name}.")
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(CONNECT_TIMEOUT_SECONDS)
        try:
            client.connect(str(path))
        except TimeoutError as error:
            raise ValueError(f"Timed out connecting to daemon for {name}.") from error
        except OSError as error:
            path.unlink(missing_ok=True)
            socket_record(config, name).unlink(missing_ok=True)
            raise ValueError(f"No daemon is running for {name}.") from error
        try:
            client.sendall((json.dumps(message) + "\n").encode())
            if message.get("command") in ("start", "restart"):
                client.settimeout(START_REPLY_TIMEOUT_SECONDS)
            with client.makefile("r") as replies:
                line = replies.readline()
        except TimeoutError as error:
            raise ValueError(
                f"Daemon for {name} timed out waiting for a reply. "
                "The command may still be running; do not retry it."
            ) from error
        except OSError as error:
            raise ValueError(
                f"Lost the reply from daemon for {name}. "
                "The command may still be running; do not retry it."
            ) from error
    if not line:
        raise ValueError(f"Daemon for {name} closed without a reply.")
    reply: dict[str, object] = json.loads(line)
    return reply
