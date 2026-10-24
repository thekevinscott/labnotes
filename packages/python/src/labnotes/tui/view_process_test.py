import asyncio
import shlex
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest import mock

import pytest

from labnotes.tui.view_process import ViewProcess

ECHO = """
import json, os, sys
for line in sys.stdin:
    request = json.loads(line)
    if request.get("wait"):
        import time; time.sleep(request["wait"])
    print(json.dumps({**request, "pid": os.getpid(), "cwd": os.getcwd()}), flush=True)
"""


def command(code: str) -> str:
    return shlex.join([sys.executable, "-c", code])


def run[T](test: Callable[[], Awaitable[T]]) -> T:
    return asyncio.run(test())  # type: ignore[arg-type]


def test_answers_a_request_from_the_project_root(tmp_path: Path) -> None:
    async def test() -> tuple[str, float]:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            return await view.request({"n": 1})
        finally:
            await view.close()

    reply, elapsed = run(test)

    assert reply.endswith("}\n")
    assert '"n": 1' in reply
    assert f'"cwd": "{tmp_path}"' in reply
    assert 0 < elapsed < 5


def test_starts_the_command_once(tmp_path: Path) -> None:
    async def test() -> list[str]:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            return [(await view.request({"n": n}))[0] for n in range(2)]
        finally:
            await view.close()

    first, second = run(test)

    assert (
        first.split('"pid": ')[1].split(",")[0]
        == second.split('"pid": ')[1].split(",")[0]
    )


def test_times_the_reply(tmp_path: Path) -> None:
    async def test() -> float:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            await view.request({})
            return (await view.request({"wait": 0.2}))[1]
        finally:
            await view.close()

    assert run(test) >= 0.2


def test_sends_one_request_at_a_time(tmp_path: Path) -> None:
    async def test() -> list[str]:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            replies = await asyncio.gather(
                view.request({"n": 0, "wait": 0.1}), view.request({"n": 1})
            )
            return [reply for reply, _ in replies]
        finally:
            await view.close()

    first, second = run(test)

    assert '"n": 0' in first
    assert '"n": 1' in second


def test_a_cancelled_caller_leaves_the_stream_in_step(tmp_path: Path) -> None:
    async def test() -> str:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            gone = asyncio.ensure_future(view.request({"n": 0, "wait": 0.1}))
            await asyncio.sleep(0.05)
            gone.cancel()
            return (await view.request({"n": 1}))[0]
        finally:
            await view.close()

    assert '"n": 1' in run(test)


def test_reports_a_view_that_stopped_with_its_last_error(tmp_path: Path) -> None:
    code = "import sys\nsys.stdin.readline()\nprint('first\\nboom\\n', file=sys.stderr)"

    async def test() -> None:
        view = ViewProcess(command(code), tmp_path)
        try:
            await view.request({})
        finally:
            await view.close()

    with pytest.raises(ValueError) as error:
        run(test)

    assert str(error.value) == "the runs view stopped: boom"


def test_reports_a_silent_stop(tmp_path: Path) -> None:
    async def test() -> None:
        view = ViewProcess(command("pass"), tmp_path)
        await view.request({})

    with pytest.raises(ValueError) as error:
        run(test)

    assert str(error.value) == "the runs view stopped"


def test_reads_long_replies(tmp_path: Path) -> None:
    async def test() -> str:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            return (await view.request({"big": "x" * 300_000}))[0]
        finally:
            await view.close()

    assert len(run(test)) > 300_000


def test_close_ends_the_view_by_closing_its_input(tmp_path: Path) -> None:
    async def test() -> int | None:
        view = ViewProcess(command(ECHO), tmp_path)
        await view.request({})
        await view.close()
        await view.close()
        assert view.process is not None
        return view.process.returncode

    assert run(test) == 0


def test_close_kills_a_view_that_ignores_its_input(tmp_path: Path) -> None:
    code = "import sys, time\nsys.stdin.readline()\nprint('{}', flush=True)\ntime.sleep(60)"

    async def test() -> int | None:
        view = ViewProcess(command(code), tmp_path)
        await view.request({})
        with mock.patch("labnotes.tui.view_process.GRACE_SECONDS", 0.1):
            await view.close()
        assert view.process is not None
        return view.process.returncode

    assert run(test) == -9


def test_close_before_any_request_does_nothing(tmp_path: Path) -> None:
    async def test() -> None:
        view = ViewProcess(command(ECHO), tmp_path)
        await view.close()
        assert view.process is None

    run(test)


def test_times_the_reply_from_when_it_was_sent(tmp_path: Path) -> None:
    async def test() -> float:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            with mock.patch("labnotes.tui.view_process.time") as clock:
                clock.monotonic.side_effect = [10.0, 30.25]
                return (await view.request({}))[1]
        finally:
            await view.close()

    assert run(test) == 20.25


def test_reads_replies_up_to_one_gibibyte(tmp_path: Path) -> None:
    spawn = mock.AsyncMock(wraps=asyncio.create_subprocess_shell)

    async def test() -> None:
        view = ViewProcess(command(ECHO), tmp_path)
        try:
            with mock.patch("asyncio.create_subprocess_shell", spawn):
                await view.request({})
        finally:
            await view.close()

    run(test)

    assert spawn.call_args.kwargs["limit"] == 1024**3


def test_waits_a_second_for_the_last_error_of_a_stopped_view(tmp_path: Path) -> None:
    code = (
        "import os, sys, time\nsys.stdin.readline()\nos.close(1)\n"
        "time.sleep(0.5)\nprint('late', file=sys.stderr, flush=True)\ntime.sleep(60)"
    )

    async def test() -> float:
        # Without exec, sh holds the closed stdout open until the script exits.
        view = ViewProcess(f"exec {command(code)}", tmp_path)
        started = time.monotonic()
        try:
            with pytest.raises(ValueError) as error:
                await view.request({})
            assert str(error.value) == "the runs view stopped: late"
            return time.monotonic() - started
        finally:
            assert view.process is not None
            view.process.kill()
            await view.process.wait()

    assert 1.0 <= run(test) < 1.5


def test_close_kills_a_view_after_a_second(tmp_path: Path) -> None:
    code = "import sys, time\nsys.stdin.readline()\nprint('{}', flush=True)\ntime.sleep(60)"

    async def test() -> float:
        view = ViewProcess(command(code), tmp_path)
        await view.request({})
        started = time.monotonic()
        await view.close()
        return time.monotonic() - started

    assert 1.0 <= run(test) < 1.5
