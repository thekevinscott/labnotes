import asyncio
import json
from pathlib import Path


async def is_retryable(
    command: str,
    cwd: Path,
    attempt: dict[str, object],
    log: Path,
    env: dict[str, str],
    running: set[asyncio.subprocess.Process],
) -> bool:
    with log.open("ab") as output:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=output,
                stderr=output,
                env=env,
            )
        except OSError:
            return False
        running.add(process)
        try:
            await process.communicate(json.dumps(attempt).encode())
        finally:
            running.discard(process)
    return process.returncode == 0
