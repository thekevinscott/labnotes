import asyncio
from unittest import mock

from labnotes.runner.drain_output import DRAIN_SECONDS, drain_output


def test_waits_for_each_copy_to_reach_the_end() -> None:
    finished: list[str] = []

    async def copy(name: str, seconds: float) -> None:
        await asyncio.sleep(seconds)
        finished.append(name)

    async def go() -> None:
        await drain_output(
            [
                asyncio.create_task(copy("stdout", 0.05)),
                asyncio.create_task(copy("stderr", 0)),
            ]
        )

    asyncio.run(go())

    assert finished == ["stderr", "stdout"]


def test_stops_a_copy_still_open_after_the_grace() -> None:
    async def hold() -> None:
        await asyncio.Event().wait()

    async def go() -> tuple[bool, bool]:
        done = asyncio.create_task(asyncio.sleep(0))
        held = asyncio.create_task(hold())
        with mock.patch("labnotes.runner.drain_output.DRAIN_SECONDS", 0.05):
            await drain_output([done, held])
        return done.cancelled(), held.cancelled()

    assert asyncio.run(go()) == (False, True)


def test_a_failed_copy_does_not_fail_the_run() -> None:
    async def fail() -> None:
        raise OSError("disk full")

    async def go() -> None:
        await drain_output([asyncio.create_task(fail())])

    asyncio.run(go())


def test_gives_lingering_helpers_two_seconds() -> None:
    assert DRAIN_SECONDS == 2
