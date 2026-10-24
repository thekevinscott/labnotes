import asyncio
import json
import time
from pathlib import Path

from labnotes.utils.tree_usage import tree_usage


async def record_memory(path: Path, pid: int, created: float, interval: float) -> None:
    with path.open("a", encoding="utf-8") as samples:
        while True:
            usage = tree_usage(pid, created)
            if usage is not None:
                rss, processes = usage
                sample = {"time": time.time(), "rss": rss, "processes": processes}
                samples.write(json.dumps(sample) + "\n")
                samples.flush()
            await asyncio.sleep(interval)
