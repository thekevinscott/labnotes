"""Send one command to a live daemon over HTTP and return its reply."""

import json
from collections.abc import Callable
from typing import cast

import httpx2

from labnotes.daemon.client import daemon_socket
from labnotes.daemon.socket_path import socket_record
from labnotes.models import LabnotesConfig

ROUTES = {
    "stop_all": "/stop",
    "finish_up": "/finish-up",
    "set_concurrency": "/concurrency",
}


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
    fields = dict(message)
    fields.pop("command", None)
    read: int | None = 10
    body: object
    match action:
        case "batches":
            method, route, body = "GET", "/batches", None
        case "start" | "restart":
            method, route, body = "POST", f"/{action}", message.get("options", {})
            read = None
        case "stop_one" | "start_one":
            run, verb = message.get("run"), action.removesuffix("_one")
            method, route, body = "POST", f"/runs/{run}/{verb}", fields
        case _:
            method, route, body = "POST", ROUTES[action], fields
    reply: object = None
    try:
        with httpx2.Client(
            transport=httpx2.HTTPTransport(uds=str(path)),
            base_url="http://labnotes",
            timeout=httpx2.Timeout(10, read=read),
        ) as client:
            with client.stream(method, route, json=body) as response:
                if response.headers.get("content-type", "").startswith(
                    "text/event-stream"
                ):
                    for event in httpx2.EventSource(response):
                        match event.event:
                            case "step" if progress is not None:
                                progress(str(event.json()))
                            case "reply":
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
