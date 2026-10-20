from pathlib import Path

from labnotes.daemon.daemon_client import daemon_client
from labnotes.daemon.daemon_running import daemon_running


async def control_run(
    root: Path, name: str, action: str, args: list[object]
) -> str | None:
    if not await daemon_running(root):
        return "Nothing is running."
    async with daemon_client(root) as client:
        reply = await client.post(f"/experiments/{name}/{action}", json={"args": args})
    if reply.is_success:
        return None
    return str(reply.json()["error"])
