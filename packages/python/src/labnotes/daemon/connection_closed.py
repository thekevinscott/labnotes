"""Wait for a held daemon connection to end."""

import asyncio
import socket


async def connection_closed(client: socket.socket) -> None:
    """Return once the peer closes the connection or it fails."""
    client.setblocking(False)
    loop = asyncio.get_running_loop()
    try:
        while await loop.sock_recv(client, 1024):
            pass
    except OSError:
        pass
