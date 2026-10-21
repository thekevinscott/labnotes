import asyncio
from collections.abc import AsyncIterator

from labnotes.tui.reload_on_change import reload_on_change


END = object()


async def settle() -> None:
    await asyncio.sleep(0.01)


class Harness:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[object] = asyncio.Queue()
        self.reloads = 0
        self.gate = asyncio.Event()
        self.gate.set()
        self.closed = False
        self.stops: list[BaseException | None] = []

    async def changes(self) -> AsyncIterator[object]:
        try:
            while True:
                change = await self.queue.get()
                if change is END:
                    return
                if isinstance(change, BaseException):
                    raise change
                yield change
        finally:
            self.closed = True

    async def reload(self) -> None:
        self.reloads += 1
        await self.gate.wait()

    def stopped(self, error: BaseException | None) -> None:
        self.stops.append(error)

    def start(self) -> asyncio.Task[None]:
        return asyncio.create_task(
            reload_on_change(self.changes(), self.reload, self.stopped)
        )


def test_loads_at_once_then_again_on_each_change() -> None:
    async def scenario() -> list[int]:
        harness = Harness()
        task = harness.start()
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
        task = harness.start()
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
        task = harness.start()
        await settle()
        task.cancel()
        await settle()
        return harness.closed

    assert asyncio.run(scenario()) is True


def test_reloads_once_more_then_reports_why_the_watch_failed() -> None:
    error = OSError("watcher died")

    async def scenario() -> tuple[int, list[BaseException | None], bool]:
        harness = Harness()
        task = harness.start()
        await settle()
        harness.queue.put_nowait("row")
        harness.queue.put_nowait(error)
        await settle()
        return harness.reloads, harness.stops, task.done()

    assert asyncio.run(scenario()) == (2, [error], True)


def test_reports_a_watch_that_ends() -> None:
    async def scenario() -> list[BaseException | None]:
        harness = Harness()
        task = harness.start()
        await settle()
        harness.queue.put_nowait(END)
        await task
        return harness.stops

    assert asyncio.run(scenario()) == [None]
