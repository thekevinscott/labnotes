"""Exchange one JSON command and one reply with a live daemon."""

import json
import socket
from collections.abc import Callable

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import socket_record
from labnotes.models import LabnotesConfig

STARTS = ("start", "restart")


def command(
    config: LabnotesConfig,
    name: str,
    message: dict[str, object],
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Send a request and read its reply, passing step lines to progress.

    A start has no reply deadline: preparing a large project can take
    minutes, and the daemon closing the socket ends the wait instead.
    """
    path = daemon_socket(config, name)
    if path is None:
        raise ValueError(f"No daemon is running for {name}.")
    reply: dict[str, object] | None = None
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(10)
        try:
            client.connect(str(path))
        except TimeoutError as error:
            raise ValueError(f"Daemon for {name} did not answer in 10s.") from error
        except OSError as error:
            path.unlink(missing_ok=True)
            socket_record(config, name).unlink(missing_ok=True)
            raise ValueError(f"No daemon is running for {name}.") from error
        # Past connect the daemon is alive, so its socket and record stay.
        try:
            client.sendall((json.dumps(message) + "\n").encode())
            if message.get("command") in STARTS:
                client.settimeout(None)
            with client.makefile("r") as replies:
                for line in replies:
                    reply = json.loads(line)
                    if "step" not in reply:
                        break
                    if progress is not None:
                        progress(str(reply["step"]))
                    reply = None
        except TimeoutError as error:
            raise ValueError(f"Daemon for {name} did not reply in 10s.") from error
        except OSError:
            reply = None
    if reply is None:
        raise ValueError(f"Daemon for {name} closed without a reply.")
    return reply
