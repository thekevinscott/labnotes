from pathlib import Path

import httpx2

from labnotes.daemon.socket_path import socket_path


def daemon_client(root: Path) -> httpx2.AsyncClient:
    transport = httpx2.AsyncHTTPTransport(uds=str(socket_path(root)))
    return httpx2.AsyncClient(
        transport=transport, base_url="http://labnotes", timeout=None
    )
