import asyncio

import pytest
from textual.app import App, ComposeResult

from labnotes.tui.runs_table import RunsTable


class TableApp(App[None]):
    def compose(self) -> ComposeResult:
        yield RunsTable(cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(RunsTable)
        table.add_column("run")
        table.add_rows([["r1"], ["r2"], ["r3"]])


@pytest.mark.parametrize(
    ("keys", "row"),
    [(("j",), 1), (("j", "j", "k"), 1), (("G",), 2), (("G", "g"), 0)],
)
def test_moves_the_cursor_with_vim_keys(keys: tuple[str, ...], row: int) -> None:
    async def drive() -> None:
        app = TableApp()
        async with app.run_test() as pilot:
            await pilot.press(*keys)
            assert app.query_one(RunsTable).cursor_row == row

    asyncio.run(drive())
