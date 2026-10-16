import asyncio
import hashlib
from pathlib import Path

from jupyter_client.asynchronous.client import AsyncKernelClient
from jupyter_client.manager import AsyncKernelManager

from labnotes.output_html import output_html

QUIET = {"status", "execute_input"}


def block_key(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class NotebookKernel:
    """One live Python kernel per notes file; blocks run only when asked."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.outputs: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._manager: AsyncKernelManager | None = None
        self._client: AsyncKernelClient | None = None

    async def _start(self) -> None:
        self._manager = AsyncKernelManager(kernel_name="python3")
        await self._manager.start_kernel(cwd=str(self.cwd))
        self._client = self._manager.client()
        self._client.start_channels()
        await self._client.wait_for_ready(timeout=60)

    async def run(self, code: str) -> str:
        async with self._lock:
            if self._client is None:
                await self._start()
            assert self._client is not None
            messages: list[dict[str, object]] = []
            await self._client.execute_interactive(
                code,
                output_hook=lambda message: messages.append(message),
                allow_stdin=False,
            )
            html = output_html(
                [
                    {"msg_type": message["msg_type"], "content": message["content"]}
                    for message in messages
                    if message["msg_type"] not in QUIET
                ]
            )
            self.outputs[block_key(code)] = html
            return html

    async def stop(self) -> None:
        if self._client is not None:
            self._client.stop_channels()
        if self._manager is not None:
            await self._manager.shutdown_kernel(now=True)
