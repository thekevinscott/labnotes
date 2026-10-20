import asyncio
import subprocess
import sys

from labnotes.daemon.daemon_running import daemon_running
from labnotes.models import LabnotesConfig

START_SECONDS = 10


async def ensure_daemon(config: LabnotesConfig) -> None:
    if await daemon_running(config.root):
        return
    subprocess.Popen(
        [sys.executable, "-m", "labnotes", "-c", str(config.path.resolve()), "daemon"],
        cwd=config.root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(START_SECONDS * 10):
        await asyncio.sleep(0.1)
        if await daemon_running(config.root):
            return
    raise ValueError(f"The labnotes daemon did not start in {START_SECONDS}s.")
