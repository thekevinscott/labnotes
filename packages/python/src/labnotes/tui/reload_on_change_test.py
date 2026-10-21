import asyncio
from collections.abc import AsyncIterator

from labnotes.tui.reload_on_change import reload_on_change


async def settle() -> None:
    await asyncio.sleep(0.01)


class Harness:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[object] = asyncio.Queue()
        self.reloads = 0
        self.gate = asyncio.Event()
        self.gate.set()
        self.closed = False

    async def changes(self) -> AsyncIterator[object]:
        try:
            while True:
                yield await self.queue.get()
        finally:
            self.closed = True

    async def reload(self) -> None:
        self.reloads += 1
        await self.gate.wait()


def test_loads_at_once_then_again_on_each_change() -> None:
    async def scenario() -> list[int]:
        harness = Harness()
        task = asyncio.create_task(reload_on_change(harness.changes(), harness.reload))
        await settle()
        seen = [harness.reloads]
        harness.queue.put_nowait("row")
        await settle()
        seen.append(harness.reloads)
        await settle()
        seen.append(harness.reloads)
        harness.queue.put_nowait("row")
        await settle()
        seen.append(harness.reloads)
        task.cancel()
        return seen

    assert asyncio.run(scenario()) == [1, 2, 2, 3]


def test_folds_changes_during_a_reload_into_one_more() -> None:
    async def scenario() -> int:
        harness = Harness()
        harness.gate.clear()
        task = asyncio.create_task(reload_on_change(harness.changes(), harness.reload))
        await settle()
        for _ in range(3):
            harness.queue.put_nowait("row")
        await settle()
        harness.gate.set()
        await settle()
        task.cancel()
        return harness.reloads

    assert asyncio.run(scenario()) == 2


def test_stops_watching_when_cancelled() -> None:
    async def scenario() -> bool:
        harness = Harness()
        task = asyncio.create_task(reload_on_change(harness.changes(), harness.reload))
        await settle()
        task.cancel()
        await settle()
        return harness.closed

    assert asyncio.run(scenario()) is True
