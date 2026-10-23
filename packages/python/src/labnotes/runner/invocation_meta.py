import asyncio
import json
from pathlib import Path


async def invocation_meta(root: Path, command: str) -> dict[str, object]:
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    detail = stderr.decode(errors="replace").strip()

    def fail(reason: str) -> ValueError:
        message = f"meta command {command} {reason}"
        return ValueError(f"{message}: {detail}" if detail else message)

    if process.returncode != 0:
        raise fail(f"exited {process.returncode}")
    try:
        meta = json.loads(stdout)
    except ValueError:
        meta = None
    if not isinstance(meta, dict):
        raise fail("didn't print a JSON object")
    return meta
