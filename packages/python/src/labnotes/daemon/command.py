"""Send one command to a live daemon over HTTP and return its reply."""

import json
from collections.abc import Callable
from typing import cast

import httpx2

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import socket_record
from labnotes.models import LabnotesConfig

ROUTES = {
    "batches": ("GET", "/batches"),
    "start": ("POST", "/start"),
    "restart": ("POST", "/restart"),
    "stop_all": ("POST", "/stop"),
    "finish_up": ("POST", "/finish-up"),
    "set_concurrency": ("POST", "/concurrency"),
}
RUN_ROUTES = {"stop_one": "stop", "start_one": "start"}


def command(
    config: LabnotesConfig,
    name: str,
    message: dict[str, object],
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Send a request and read its reply, passing start steps to progress.

    A start has no reply deadline: preparing a large project can take
    minutes, and the daemon closing the socket ends the wait instead.
    """
    path = daemon_socket(config, name)
    if path is None:
        raise ValueError(f"No daemon is running for {name}.")
    action = str(message.get("command"))
    if action in RUN_ROUTES:
        method, route = "POST", f"/runs/{message.get('run')}/{RUN_ROUTES[action]}"
    else:
        method, route = ROUTES[action]
    starts = action in ("start", "restart")
    body = (
        message.get("options", {})
        if starts
        else {key: value for key, value in message.items() if key != "command"}
    )
    reply: object = None
    try:
        with httpx2.Client(
            transport=httpx2.HTTPTransport(uds=str(path)),
            base_url="http://labnotes",
            timeout=httpx2.Timeout(10, read=None if starts else 10),
        ) as client:
            with client.stream(
                method, route, json=None if method == "GET" else body
            ) as response:
                if response.headers.get("content-type", "").startswith(
                    "text/event-stream"
                ):
                    for event in httpx2.EventSource(response):
                        if event.event == "step" and progress is not None:
                            progress(str(event.json()))
                        if event.event == "reply":
                            reply = event.json()
                else:
                    reply = json.loads(response.read())
    except httpx2.ConnectTimeout as error:
        raise ValueError(f"Daemon for {name} did not answer in 10s.") from error
    except httpx2.ConnectError as error:
        path.unlink(missing_ok=True)
        socket_record(config, name).unlink(missing_ok=True)
        raise ValueError(f"No daemon is running for {name}.") from error
    except httpx2.TimeoutException as error:
        raise ValueError(f"Daemon for {name} did not reply in 10s.") from error
    except (httpx2.TransportError, ValueError):
        reply = None
    if not isinstance(reply, dict):
        raise ValueError(f"Daemon for {name} closed without a reply.")
    return cast(dict[str, object], reply)
