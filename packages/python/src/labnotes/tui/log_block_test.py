import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from textual.app import App, ComposeResult
from textual.pilot import Pilot

from labnotes.tui.log_block import LogBlock

LONG = "first line of a long thought\nsecond line " + "word " * 40


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield LogBlock(LONG)


def mounted(
    check: Callable[[Pilot[None], LogBlock], Coroutine[Any, Any, None]],
) -> None:
    async def drive() -> None:
        app = Host()
        async with app.run_test(size=(40, 20)) as pilot:
            await pilot.pause()
            await check(pilot, app.query_one(LogBlock))

    asyncio.run(drive())


def shown(block: LogBlock) -> str:
    return str(block.render())


def test_starts_collapsed_to_one_line() -> None:
    async def check(_: Pilot[None], block: LogBlock) -> None:
        assert not block.expanded
        assert shown(block) == "▸ " + LONG.replace("\n", " ")
        assert block.size.height == 1

    mounted(check)


def test_click_expands_and_collapses() -> None:
    async def check(pilot: Pilot[None], block: LogBlock) -> None:
        await pilot.click(LogBlock)
        await pilot.pause()
        assert block.expanded
        assert shown(block) == "▾ " + LONG
        assert block.size.height > 2

        await pilot.click(LogBlock)
        await pilot.pause()
        assert not block.expanded
        assert block.size.height == 1

    mounted(check)


def test_grows_in_place() -> None:
    async def check(pilot: Pilot[None], block: LogBlock) -> None:
        block.extend(" more")
        await pilot.pause()
        assert block.body == LONG + " more"
        assert shown(block) == "▸ " + (LONG + " more").replace("\n", " ")

    mounted(check)


def test_shows_markup_as_text() -> None:
    async def check(pilot: Pilot[None], block: LogBlock) -> None:
        block.extend("[bold]x[/bold]")
        await pilot.pause()
        assert shown(block).endswith("[bold]x[/bold]")

    mounted(check)
