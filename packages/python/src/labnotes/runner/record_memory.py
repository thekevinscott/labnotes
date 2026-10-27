import asyncio
import json
import time
from pathlib import Path

from labnotes.runner.container_memory import ContainerMemory
from labnotes.utils.tree_usage import tree_usage


async def record_memory(path: Path, pid: int, created: float, interval: float) -> None:
    containers = ContainerMemory(path.parent.name)
    try:
        await containers.start()
        with path.open("a", encoding="utf-8") as samples:
            while True:
                usage = tree_usage(pid, created)
                if usage is not None:
                    rss, processes = usage
                    sample = {
                        "time": time.time(),
                        "rss": rss + containers.usage(),
                        "processes": processes,
                    }
                    samples.write(json.dumps(sample) + "\n")
                    samples.flush()
                await asyncio.sleep(interval)
    finally:
        await containers.close()
