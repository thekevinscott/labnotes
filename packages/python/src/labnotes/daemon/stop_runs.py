from pathlib import Path

from labnotes.daemon.daemon_client import daemon_client
from labnotes.daemon.daemon_running import daemon_running


async def stop_runs(root: Path) -> bool:
    if not await daemon_running(root):
        return False
    async with daemon_client(root) as client:
        (await client.post("/stop")).raise_for_status()
    return True
