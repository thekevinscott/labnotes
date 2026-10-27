import asyncio
from pathlib import Path


async def invocation_hook(root: Path, hook: str, command: str) -> None:
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=root,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        message = f"{hook} command {command} exited {process.returncode}"
        detail = stderr.decode(errors="replace").strip()
        raise ValueError(f"{message}: {detail}" if detail else message)
