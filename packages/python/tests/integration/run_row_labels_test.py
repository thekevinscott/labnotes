import asyncio

from textual.app import App, ComposeResult

from labnotes.tui.runs_table import RunsTable


def test_row_labels_survive_a_paint_between_clearing_and_idle() -> None:
    class Host(App[None]):
        def compose(self) -> ComposeResult:
            yield RunsTable()

    async def drive() -> str:
        app = Host()
        async with app.run_test() as pilot:
            table = app.query_one(RunsTable)
            table.add_column("run", key="run")
            table.add_row("a", key="a", label="1")
            await pilot.pause()
            table.clear()
            table.add_row("a", key="a", label="1")
            table.render_line(1)
            await pilot.pause()
            table.refresh()
            await pilot.pause()
            return "".join(segment.text for segment in table.render_line(1))

    assert asyncio.run(drive()).split() == ["1", "a"]
