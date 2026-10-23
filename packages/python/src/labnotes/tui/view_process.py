import asyncio
import json
import signal
import time
from pathlib import Path
from typing import Any

from labnotes.runner.signal_tree import signal_tree

# Replies carry every requested row on one line.
LINE_LIMIT = 1 << 30
GRACE_SECONDS = 1.0


class ViewProcess:
    """Hold one view worker for the life of labnotes, one request at a time."""

    def __init__(self, command: str, root: Path) -> None:
        self.command = command
        self.root = root
        self.process: asyncio.subprocess.Process | None = None
        self.stderr: asyncio.Task[None] | None = None
        self.last_error = ""
        self.lock = asyncio.Lock()

    def request(self, payload: dict[str, Any]) -> asyncio.Future[tuple[str, float]]:
        # A cancelled caller must not leave its reply for the next request.
        return asyncio.shield(self.locked(payload))

    async def locked(self, payload: dict[str, Any]) -> tuple[str, float]:
        async with self.lock:
            return await self.exchange(payload)

    async def exchange(self, payload: dict[str, Any]) -> tuple[str, float]:
        if self.process is None:
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                cwd=self.root,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=LINE_LIMIT,
            )
            self.stderr = asyncio.create_task(self.read_stderr(self.process.stderr))
        stdin, stdout, stderr = self.process.stdin, self.process.stdout, self.stderr
        assert stdin is not None and stdout is not None and stderr is not None
        started = time.monotonic()
        stdin.write(json.dumps(payload).encode() + b"\n")
        await stdin.drain()
        reply = await stdout.readline()
        elapsed = time.monotonic() - started
        if not reply:
            await asyncio.wait([stderr], timeout=GRACE_SECONDS)
            detail = f": {self.last_error}" if self.last_error else ""
            raise ValueError(f"the runs view stopped{detail}")
        return reply.decode(), elapsed

    async def read_stderr(self, stderr: asyncio.StreamReader | None) -> None:
        assert stderr is not None
        async for line in stderr:
            if text := line.decode(errors="replace").strip():
                self.last_error = text

    async def close(self) -> None:
        process = self.process
        if process is None or process.returncode is not None:
            return
        assert process.stdin is not None
        process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), GRACE_SECONDS)
        except TimeoutError:
            # A shell or uv wrapper would leave the script itself behind.
            signal_tree(process.pid, signal.SIGKILL, set())
            await process.wait()
