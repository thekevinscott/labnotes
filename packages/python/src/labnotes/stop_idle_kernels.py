import asyncio
from collections.abc import Mapping

from labnotes.notebook_kernel import NotebookKernel


async def stop_idle_kernels(
    kernels: Mapping[tuple[str, str], NotebookKernel], idle_minutes: float
) -> None:
    while True:
        await asyncio.sleep(60)
        for kernel in list(kernels.values()):
            await kernel.stop_if_idle(idle_minutes * 60)
