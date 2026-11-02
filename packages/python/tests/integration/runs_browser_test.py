import asyncio
import sys
from pathlib import Path
from types import MappingProxyType

from textual.app import App, ComposeResult
from textual.widgets import DataTable

from labnotes.tui.run_panel import RunPanel
from labnotes.tui.runs_browser import RunsBrowser
from labnotes.view import Changed, Experiment, Group

RUNS = {
    "alpha/runs/a": {"id": "a", "folder": "alpha/runs/a", "status": "passed"},
    "alpha/runs/b": {"id": "b", "folder": "alpha/runs/b", "status": "failed"},
}
COLUMN = """\
from labnotes import view


@view.serve
def runs(columns):
    return [*columns, "shout"], lambda row: {**row, "shout": row["id"].upper()}
"""


class Bare(App[None]):
    def compose(self) -> ComposeResult:
        yield RunsBrowser()


def rows(app: App[None]) -> list[list[str]]:
    table = app.query_one(DataTable)
    return [
        [str(cell) for cell in table.get_row_at(number)]
        for number in range(table.row_count)
    ]


def test_shows_the_runs_from_changed_alone(tmp_path: Path) -> None:
    (tmp_path / "alpha/runs/b").mkdir(parents=True)
    experiment = Experiment(tmp_path, "alpha", RUNS)
    app = Bare()

    async def drive() -> None:
        async with app.run_test() as pilot:
            app.query_one(RunsBrowser).post_message(Changed(experiment))
            await pilot.pause()

            assert rows(app) == [["✓", "a", "", ""], ["✕", "b", "", ""]]

            app.query_one(DataTable).focus()
            await pilot.press("down", "enter")
            await pilot.pause()

            assert app.query_one(RunPanel).run_id == "b"

    asyncio.run(drive())


def test_starts_its_own_column_script(tmp_path: Path) -> None:
    (tmp_path / "view.py").write_text(COLUMN)
    command = f"{sys.executable} view.py"
    config = {"views": {"runs": command}}
    experiment = Experiment(tmp_path, "alpha", RUNS, MappingProxyType(config))
    app = Bare()

    async def drive() -> None:
        async with app.run_test() as pilot:
            app.query_one(RunsBrowser).post_message(Changed(experiment))
            for _ in range(50):
                await pilot.pause(0.1)
                if rows(app) == [["✓", "a", "", "", "A"], ["✕", "b", "", "", "B"]]:
                    break

            assert rows(app) == [["✓", "a", "", "", "A"], ["✕", "b", "", "", "B"]]
            process = app.query_one(RunsBrowser).process
            assert process is not None
        assert process.process is not None
        assert process.process.returncode is not None

    asyncio.run(drive())


INVOCATION = {
    f"alpha/runs/20261017-000000/{name}": {
        "id": f"20261017-000000/{name}",
        "status": status,
        "m": 1,
    }
    for name, status in [("x", "passed"), ("y", "failed"), ("z", "passed")]
}


def test_counts_each_invocation_from_its_runs(tmp_path: Path) -> None:
    experiment = Experiment(
        tmp_path,
        "alpha",
        INVOCATION,
        MappingProxyType({"params": {"m": [1, 2]}}),
        groups=(Group("20261017-000000", tuple(INVOCATION), False),),
    )
    app = Bare()

    async def drive() -> None:
        async with app.run_test() as pilot:
            app.query_one(RunsBrowser).post_message(Changed(experiment))
            await pilot.pause()

            assert rows(app) == [
                ["2✓ 1✕", "▸ 20261017-000000", "3", "1", "2026-10-17 00:00:00", ""]
            ]

    asyncio.run(drive())
