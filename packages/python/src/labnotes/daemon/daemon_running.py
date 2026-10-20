import asyncio
from pathlib import Path

from labnotes.daemon.socket_path import socket_path


async def daemon_running(root: Path) -> bool:
    try:
        _, writer = await asyncio.open_unix_connection(socket_path(root))
    except (FileNotFoundError, ConnectionRefusedError):
        return False
    writer.close()
    await writer.wait_closed()
    return True
