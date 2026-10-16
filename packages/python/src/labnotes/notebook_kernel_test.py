import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.notebook_kernel import NotebookKernel, block_key


def reply_with(*messages: dict[str, object]) -> Callable[..., object]:
    async def execute_interactive(
        code: str, output_hook: Callable[[object], None], **_: object
    ) -> dict[str, object]:
        for message in messages:
            output_hook(message)
        return {"content": {"status": "ok"}}

    return execute_interactive


@pytest.fixture
def manager() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.notebook_kernel.AsyncKernelManager") as cls:
        instance = cls.return_value
        instance.start_kernel = mock.AsyncMock()
        instance.shutdown_kernel = mock.AsyncMock()
        client = instance.client.return_value
        client.wait_for_ready = mock.AsyncMock()
        client.execute_interactive = mock.AsyncMock(
            side_effect=reply_with(
                {"msg_type": "status", "content": {}},
                {"msg_type": "stream", "content": {"name": "stdout", "text": "hi"}},
            )
        )
        yield cls


def test_starts_lazily_in_the_given_folder_and_runs_the_code(
    manager: mock.MagicMock,
) -> None:
    kernel = NotebookKernel(Path("/data"))
    manager.assert_not_called()

    html = asyncio.run(kernel.run("print('hi')"))

    assert html == '<pre class="stdout">hi</pre>'
    manager.assert_called_once_with(kernel_name="python3")
    manager.return_value.start_kernel.assert_awaited_once_with(cwd="/data")
    client = manager.return_value.client.return_value
    client.start_channels.assert_called_once_with()
    client.wait_for_ready.assert_awaited_once_with(timeout=60)
    assert client.execute_interactive.await_args.args == ("print('hi')",)
    assert client.execute_interactive.await_args.kwargs["allow_stdin"] is False


def test_reuses_the_kernel_and_remembers_outputs_by_code(
    manager: mock.MagicMock,
) -> None:
    kernel = NotebookKernel(Path("/data"))

    async def twice() -> None:
        await kernel.run("a")
        await kernel.run("b")

    asyncio.run(twice())

    manager.assert_called_once()
    assert set(kernel.outputs) == {block_key("a"), block_key("b")}
    assert kernel.outputs[block_key("a")] == '<pre class="stdout">hi</pre>'


def test_runs_one_block_at_a_time(manager: mock.MagicMock) -> None:
    active: list[int] = []
    peak: list[int] = []

    async def slow(code: str, output_hook: object, **_: object) -> None:
        active.append(1)
        peak.append(len(active))
        await asyncio.sleep(0)
        active.pop()

    client = manager.return_value.client.return_value
    client.execute_interactive.side_effect = slow
    kernel = NotebookKernel(Path("/data"))

    async def together() -> None:
        await asyncio.gather(kernel.run("a"), kernel.run("b"))

    asyncio.run(together())

    assert max(peak) == 1


def test_stop_shuts_a_started_kernel_down(manager: mock.MagicMock) -> None:
    kernel = NotebookKernel(Path("/data"))

    async def run_then_stop() -> None:
        await kernel.run("a")
        await kernel.stop()

    asyncio.run(run_then_stop())

    manager.return_value.client.return_value.stop_channels.assert_called_once()
    manager.return_value.shutdown_kernel.assert_awaited_once_with(now=True)


def test_stop_without_a_kernel_does_nothing(manager: mock.MagicMock) -> None:
    asyncio.run(NotebookKernel(Path("/data")).stop())

    manager.assert_not_called()


def test_block_key_is_stable_per_code() -> None:
    assert block_key("x") == block_key("x") != block_key("y")


def test_a_stopped_kernel_starts_fresh_on_the_next_run_and_keeps_outputs(
    manager: mock.MagicMock,
) -> None:
    kernel = NotebookKernel(Path("/data"))

    async def run_stop_run() -> None:
        await kernel.run("a")
        await kernel.stop()
        await kernel.run("b")

    asyncio.run(run_stop_run())

    assert manager.return_value.start_kernel.await_count == 2
    assert set(kernel.outputs) == {block_key("a"), block_key("b")}


def test_stopping_twice_shuts_the_kernel_down_once(manager: mock.MagicMock) -> None:
    kernel = NotebookKernel(Path("/data"))

    async def run_stop_stop() -> None:
        await kernel.run("a")
        await kernel.stop()
        await kernel.stop()

    asyncio.run(run_stop_stop())

    manager.return_value.shutdown_kernel.assert_awaited_once()
    manager.return_value.client.return_value.stop_channels.assert_called_once()


def test_records_when_a_run_finishes(manager: mock.MagicMock) -> None:
    with mock.patch("labnotes.notebook_kernel.monotonic", side_effect=[5.0, 9.0]):
        kernel = NotebookKernel(Path("/data"))
        assert kernel.last_used == 5.0
        asyncio.run(kernel.run("a"))

    assert kernel.last_used == 9.0


def test_records_when_a_failed_run_finishes(manager: mock.MagicMock) -> None:
    client = manager.return_value.client.return_value
    client.execute_interactive.side_effect = RuntimeError("boom")
    with mock.patch("labnotes.notebook_kernel.monotonic", side_effect=[5.0, 9.0]):
        kernel = NotebookKernel(Path("/data"))
        with pytest.raises(RuntimeError):
            asyncio.run(kernel.run("a"))

    assert kernel.last_used == 9.0


@pytest.mark.parametrize(
    ("now", "stopped"),
    [(120.0, False), (160.0, False), (160.5, True), (1000.0, True)],
)
def test_stops_a_kernel_idle_longer_than_the_limit(
    manager: mock.MagicMock, now: float, stopped: bool
) -> None:
    kernel = NotebookKernel(Path("/data"))
    asyncio.run(kernel.run("a"))
    kernel.last_used = 100.0

    with mock.patch("labnotes.notebook_kernel.monotonic", return_value=now):
        asyncio.run(kernel.stop_if_idle(60))

    assert manager.return_value.shutdown_kernel.await_count == int(stopped)


def test_never_stops_a_kernel_mid_run(manager: mock.MagicMock) -> None:
    kernel = NotebookKernel(Path("/data"))
    checked: list[int] = []

    async def idle_check_while_running(
        code: str, output_hook: object, **_: object
    ) -> None:
        await kernel.stop_if_idle(0)
        checked.append(manager.return_value.shutdown_kernel.await_count)

    client = manager.return_value.client.return_value
    client.execute_interactive.side_effect = idle_check_while_running
    kernel.last_used = -1e9

    asyncio.run(kernel.run("a"))

    assert checked == [0]


def test_restart_waits_for_the_running_block_then_stops(
    manager: mock.MagicMock,
) -> None:
    events: list[str] = []

    async def slow(code: str, output_hook: object, **_: object) -> None:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        events.append("ran")

    async def shutdown(now: bool) -> None:
        events.append("stopped")

    manager.return_value.client.return_value.execute_interactive.side_effect = slow
    manager.return_value.shutdown_kernel.side_effect = shutdown
    kernel = NotebookKernel(Path("/data"))

    async def run_and_restart() -> None:
        running = asyncio.create_task(kernel.run("a"))
        await asyncio.sleep(0)
        await kernel.restart()
        await running

    asyncio.run(run_and_restart())

    assert events == ["ran", "stopped"]
    assert block_key("a") in kernel.outputs
