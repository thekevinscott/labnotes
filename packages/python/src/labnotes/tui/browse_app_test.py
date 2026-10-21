import asyncio
import functools
from collections.abc import Callable, Coroutine, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from textual.pilot import Pilot

from labnotes.tui.browse_app import BrowseApp

CONFIG = mock.Mock(root=Path("/p/project"), mode="matrix")
EXPERIMENTS = [
    {
        "name": "alpha",
        "display_name": "Alpha",
        "last_run": "2026-10-17",
        "created": None,
        "files": 2,
        "runs": 3,
    },
    {
        "name": "beta",
        "display_name": "Beta",
        "last_run": None,
        "created": None,
        "files": 0,
        "runs": 0,
    },
]
LOADED = {
    "display_name": "Alpha study",
    "run_columns": ["id", "m"],
    "runs_live": False,
    "runs_list": [],
    "run_groups": [
        {
            "name": "inv",
            "flat": False,
            "started": None,
            "runs": [
                {
                    "id": "inv/r1",
                    "m": "a",
                    "labnotes_completed": 1,
                    "labnotes_unfinished": 0,
                }
            ],
            "shared": {"m": "a"},
            "passed": 1,
            "failed": 0,
            "unfinished": 0,
        },
        {
            "name": "lone",
            "flat": True,
            "started": None,
            "runs": [
                {
                    "id": "lone",
                    "m": "b",
                    "labnotes_completed": 0,
                    "labnotes_unfinished": 0,
                }
            ],
            "shared": {},
            "passed": 0,
            "failed": 1,
            "unfinished": 0,
        },
    ],
}


def sync(
    test: Callable[..., Coroutine[Any, Any, None]],
) -> Callable[..., None]:
    @functools.wraps(test)
    def run(*args: Any, **kwargs: Any) -> None:
        asyncio.run(test(*args, **kwargs))

    return run


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.tui.browse_app.open_tables") as open_tables,
        mock.patch(
            "labnotes.tui.experiments_screen.summarize_experiments",
            new=mock.AsyncMock(return_value=EXPERIMENTS),
        ) as summarize_experiments,
        mock.patch(
            "labnotes.tui.experiment_screen.load_experiment",
            new=mock.AsyncMock(return_value=LOADED),
        ) as load_experiment,
    ):
        yield {
            "open_tables": open_tables,
            "summarize_experiments": summarize_experiments,
            "load_experiment": load_experiment,
        }


def rows(pilot: Pilot[Any]) -> list[list[str]]:
    table: Any = pilot.app.screen.query_one("DataTable")
    return [[str(cell) for cell in table.get_row(key)] for key in table.rows]


def columns(pilot: Pilot[Any]) -> list[str]:
    table: Any = pilot.app.screen.query_one("DataTable")
    return [str(column.label) for column in table.columns.values()]


@sync
async def test_lists_the_experiments(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    app = BrowseApp(CONFIG, None)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.title == "project"
        assert columns(pilot) == [
            "name",
            "display_name",
            "last_run",
            "created",
            "files",
            "runs",
        ]
        assert rows(pilot) == [
            ["alpha", "Alpha", "2026-10-17", "", "2", "3"],
            ["beta", "Beta", "", "", "0", "0"],
        ]
    collaborators["open_tables"].assert_called_once_with(CONFIG)
    collaborators["summarize_experiments"].assert_awaited_once_with(
        collaborators["open_tables"].return_value
    )


@sync
async def test_says_when_there_are_no_experiments(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["summarize_experiments"].return_value = []
    app = BrowseApp(CONFIG, None)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.sub_title == "No experiments."
        assert rows(pilot) == []


@sync
async def test_enter_opens_an_experiment_and_escape_goes_back(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    app = BrowseApp(CONFIG, None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j", "enter")
        await pilot.pause()

        collaborators["load_experiment"].assert_awaited_once()
        assert collaborators["load_experiment"].await_args.args[:4] == (
            collaborators["open_tables"].return_value,
            CONFIG.root,
            "matrix",
            "beta",
        )
        assert app.screen.sub_title == "Alpha study"

        await pilot.press("escape")
        await pilot.pause()

        assert rows(pilot)[0][0] == "alpha"


@sync
async def test_opens_straight_on_a_named_experiment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    app = BrowseApp(CONFIG, "alpha")
    async with app.run_test() as pilot:
        await pilot.pause()

        params = collaborators["load_experiment"].await_args.args[4]
        assert params.getlist("sort") == []
        assert columns(pilot) == ["", "id", "runs", "m"]
        assert rows(pilot) == [
            ["1✓ 0✕", "inv", "1", "a"],
            ["✕", "lone", "", "b"],
        ]

        await pilot.press("escape")
        await pilot.pause()

        assert rows(pilot)[0][0] == "alpha"


@sync
async def test_space_opens_and_closes_an_invocation() -> None:
    app = BrowseApp(CONFIG, "alpha")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        assert rows(pilot) == [
            ["1✓ 0✕", "inv", "1", "a"],
            ["✓", "  r1", "", "a"],
            ["✕", "lone", "", "b"],
        ]

        await pilot.press("space")
        await pilot.pause()

        assert len(rows(pilot)) == 2


@sync
async def test_space_leaves_a_lone_run_alone() -> None:
    app = BrowseApp(CONFIG, "alpha")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j", "space")
        await pilot.pause()

        assert len(rows(pilot)) == 2
        table: Any = app.screen.query_one("DataTable")
        assert table.cursor_row == 1


@sync
async def test_space_does_nothing_without_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["load_experiment"].return_value = {
        **LOADED,
        "run_groups": None,
        "runs_list": [],
    }
    app = BrowseApp(CONFIG, "alpha")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        assert rows(pilot) == []


@sync
async def test_exits_with_an_unknown_experiment(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["load_experiment"].return_value = None
    app = BrowseApp(CONFIG, "zz")
    async with app.run_test() as pilot:
        await pilot.pause()

    assert str(app.return_value) == "No experiment named zz."


@sync
async def test_exits_when_the_experiments_cannot_be_read(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    collaborators["summarize_experiments"].side_effect = RuntimeError("bad scan")
    app = BrowseApp(CONFIG, None)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert str(app.return_value) == "bad scan"


@sync
async def test_q_quits() -> None:
    app = BrowseApp(CONFIG, None)
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()

    assert app.return_value is None
    assert not app.is_running
