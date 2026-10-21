from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.log_block import LogBlock

LONG = "first line\n[bold]second[/bold] line"


@pytest.fixture
def update() -> Iterator[mock.MagicMock]:
    with mock.patch.object(LogBlock, "update") as update:
        yield update


def shown(update: mock.MagicMock) -> str:
    return str(update.call_args.args[0].plain)


def test_starts_collapsed_to_one_line(update: mock.MagicMock) -> None:
    block = LogBlock(LONG)

    assert not block.expanded
    assert block.has_class("-collapsed")
    assert shown(update) == "▸ first line [bold]second[/bold] line"


def test_click_expands_and_collapses(update: mock.MagicMock) -> None:
    block = LogBlock(LONG)

    block.on_click(mock.Mock())
    assert block.expanded
    assert not block.has_class("-collapsed")
    assert shown(update) == f"▾ {LONG}"

    block.on_click(mock.Mock())
    assert not block.expanded
    assert block.has_class("-collapsed")
    assert shown(update) == "▸ first line [bold]second[/bold] line"


@pytest.mark.parametrize(("clicks", "text"), [(0, "▸ par tial"), (1, "▾ par\ntial")])
def test_grows_in_place(update: mock.MagicMock, clicks: int, text: str) -> None:
    block = LogBlock("par")
    for _ in range(clicks):
        block.on_click(mock.Mock())

    block.extend("\ntial")

    assert block.body == "par\ntial"
    assert shown(update) == text
