import asyncio
from collections.abc import Callable, Iterator
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.run_app import RunApp

Report = Callable[[dict[str, object]], None]
Listen = Callable[[Any], None]


@pytest.fixture(autouse=True)
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch(
            "labnotes.tui.run_app.param_args",
            side_effect=lambda params: ["--m", params["m"]],
        ),
        mock.patch(
            "labnotes.tui.run_app.describe_event",
            side_effect=lambda event: f"said {event['event']}",
        ),
        mock.patch(
            "labnotes.tui.run_app.format_elapsed",
            side_effect=lambda seconds: f"{seconds:g} seconds",
        ),
        mock.patch("labnotes.tui.run_app.time") as time,
        mock.patch("labnotes.tui.run_app.signal", mock.Mock(SIGTERM=15, SIGHUP=1)),
        mock.patch("labnotes.tui.run_app.stop_then_kill") as stop_then_kill,
    ):
        time.monotonic.return_value = 10.0
        yield {"time": time, "stop_then_kill": stop_then_kill}


def rows(app: RunApp) -> list[list[object]]:
    table: Any = app.query_one("#runs")
    return [[str(cell) for cell in table.get_row(key)] for key in table.rows]


def styles(app: RunApp) -> list[list[object]]:
    table: Any = app.query_one("#runs")
    return [
        [getattr(cell, "style", None) for cell in table.get_row(key)]
        for key in table.rows
    ]


def planned(*runs: str) -> dict[str, object]:
    return {
        "event": "planned",
        "runs": [{"run": run, "params": {"m": run}} for run in runs],
        "concurrency": 2,
    }


def status(app: RunApp) -> str:
    widget: Any = app.query_one("#status")
    return str(widget.content)


def test_shows_each_run_and_the_outcome(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        report({"event": "started", "run": "r2", "params": {"m": "b"}})
        collaborators["time"].monotonic.return_value = 34.0
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        report({"event": "ended", "run": "r2", "exit_code": None, "error": "boom"})
        return [
            {"exit_code": 0},
            {"exit_code": None},
            {"exit_code": 0},
            {"exit_code": 0},
        ]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.title == "exp"
            assert rows(app) == [
                ["r1", "--m a", "exited 0", "24 seconds"],
                ["r2", "--m b", "boom", "24 seconds"],
            ]
            assert status(app) == "3 passed, 1 failed. q to quit."
            assert len(app.results) == 4
            await pilot.press("q")
            assert not app.is_running

    asyncio.run(drive())


def test_shows_planned_runs_as_dim_pending_rows() -> None:
    rendered = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        await rendered.wait()
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered.set()
            await pilot.pause()
            assert rows(app) == [
                ["r1", "--m a", "running", "0 seconds"],
                ["r2", "--m r2", "pending", ""],
            ]
            assert styles(app) == [[None] * 4, ["dim"] * 4]
            table: Any = app.query_one("#runs")
            assert table.columns["time"].content_width == len("0 seconds")
            assert status(app) == "said planned"

    asyncio.run(drive())


def test_skips_pending_runs_when_stopping() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        report({"event": "stopping"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[2] for row in rows(app)] == ["running", "skipped", "skipped"]
            assert styles(app)[1][2] == "dim"
            assert status(app) == "said stopping"

    asyncio.run(drive())


def test_moves_queued_runs_up_the_pending_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3", "r4"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        report(
            {"event": "queued", "run": "r4", "pending": ["r4", "r2", "r3"], "held": []}
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[0] for row in rows(app)] == ["r1", "r4", "r2", "r3"]
            assert styles(app)[1] == ["dim"] * 4
            table: Any = app.query_one("#runs")
            assert table.cursor_row == 1
            assert status(app) == "said queued"

    asyncio.run(drive())


def test_moves_deselected_runs_to_the_bottom() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3", "r4"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        report(
            {
                "event": "deselected",
                "run": "r2",
                "pending": ["r3", "r4"],
                "held": ["r2"],
            }
        )
        report({"event": "stopping"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[:3:2] for row in rows(app)] == [
                ["r1", "running"],
                ["r3", "skipped"],
                ["r4", "skipped"],
                ["r2", "deselected"],
            ]
            assert styles(app)[3][2] == "dim"

    asyncio.run(drive())


def test_puts_reselected_runs_back_in_the_queue() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        report(
            {
                "event": "deselected",
                "run": "r1",
                "pending": ["r2", "r3"],
                "held": ["r1"],
            }
        )
        report(
            {
                "event": "reselected",
                "run": "r1",
                "pending": ["r2", "r3", "r1"],
                "held": [],
            }
        )
        report({"event": "stopping"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[:3:2] for row in rows(app)] == [
                ["r2", "skipped"],
                ["r3", "skipped"],
                ["r1", "skipped"],
            ]

    asyncio.run(drive())


def test_d_toggles_the_row_under_the_cursor() -> None:
    toggle = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(toggle=toggle))
        report(planned("r1", "r2"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "d")
            toggle.assert_called_once_with("r2")

    asyncio.run(drive())


def test_d_leaves_the_cursor_on_the_next_row() -> None:
    reports: list[Report] = []

    def deselect(run: str) -> None:
        reports[0](
            {"event": "deselected", "run": run, "pending": ["r1", "r3"], "held": [run]}
        )

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        listen(mock.Mock(toggle=deselect))
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "d")
            await pilot.pause()
            table: Any = app.query_one("#runs")
            assert [row[0] for row in rows(app)] == ["r1", "r3", "r2"]
            assert table.cursor_row == 1

    asyncio.run(drive())


def test_d_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        with mock.patch.object(app, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.press("d")
            controls.toggle.assert_not_called()

    asyncio.run(drive())


def test_n_runs_the_row_under_the_cursor_next() -> None:
    run_next = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(run_next=run_next))
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "n")
            run_next.assert_called_once_with("r3")

    asyncio.run(drive())


def test_n_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        with mock.patch.object(app, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.press("n")
            controls.run_next.assert_not_called()

    asyncio.run(drive())


def test_plus_and_minus_change_the_concurrency() -> None:
    set_concurrency = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(set_concurrency=set_concurrency))
        report(planned("r1"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.sub_title == "2 at a time"
            await pilot.press("plus", "equals_sign", "minus")
            assert set_concurrency.call_args_list == [
                mock.call(3),
                mock.call(3),
                mock.call(1),
            ]

    asyncio.run(drive())


def test_concurrency_starts_at_one_until_planned() -> None:
    set_concurrency = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(set_concurrency=set_concurrency))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("plus")
            set_concurrency.assert_called_once_with(2)

    asyncio.run(drive())


def test_shows_the_new_concurrency() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report({"event": "concurrency", "concurrency": 5})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert (app.concurrency, app.sub_title) == (5, "5 at a time")
            assert status(app) == "said concurrency"

    asyncio.run(drive())


def test_shows_other_events_as_status() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report({"event": "killing"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "said killing"

    asyncio.run(drive())


def test_ticks_the_time_of_running_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            collaborators["time"].monotonic.return_value = 25.0
            app.tick()
            assert rows(app) == [["r1", "--m a", "running", "15 seconds"]]

    asyncio.run(drive())


def test_ctrl_c_interrupts_the_runs_until_they_finish(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    interrupt = mock.Mock()
    finish = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(interrupt=interrupt))
        await finish.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.press("ctrl+c")
            assert interrupt.call_count == 2
            assert app.is_running
            finish.set()
            await pilot.pause()
            await pilot.press("ctrl+c")
            assert not app.is_running
            assert interrupt.call_count == 2
            collaborators["stop_then_kill"].assert_called_once_with(
                app.action_interrupt, 15, 1
            )

    asyncio.run(drive())


def test_waits_for_runs_before_quitting() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.press("q")
            assert app.is_running
            assert status(app) == "Runs are still going. Ctrl-C stops them."

    asyncio.run(drive())


def test_ticks_every_second() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return []

    async def drive() -> None:
        app = RunApp(start, "exp")
        with mock.patch.object(app, "set_interval") as set_interval:
            async with app.run_test() as pilot:
                await pilot.pause()
        set_interval.assert_called_once_with(1, app.tick)

    asyncio.run(drive())


def test_widens_columns_as_cells_grow(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    rendered = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}})
        await rendered.wait()
        collaborators["time"].monotonic.return_value = 1234.0
        report({"event": "ended", "run": "r1", "exit_code": -15, "error": None})
        return [{"exit_code": -15}]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered.set()
            await pilot.pause()
            table: Any = app.query_one("#runs")
            widths = [table.columns[key].content_width for key in ("status", "time")]
            assert widths == [len("exited -15"), len("1224 seconds")]

    asyncio.run(drive())


def test_slash_filters_rows_by_params() -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash", "2", "enter")
            assert [row[0] for row in rows(app)] == ["r2"]
            reports[0]({"event": "started", "run": "r1", "params": {"m": "r1"}})
            reports[0]({"event": "started", "run": "r2", "params": {"m": "r2"}})
            await pilot.pause()
            assert rows(app) == [["r2", "--m r2", "running", "0 seconds"]]
            assert app.query_one("#filter").display
            assert app.query_one("#runs").has_focus
            await pilot.press("escape")
            assert [row[:3] for row in rows(app)] == [
                ["r1", "--m r1", "running"],
                ["r2", "--m r2", "running"],
                ["r3", "--m r3", "pending"],
            ]
            assert not app.query_one("#filter").display

    asyncio.run(drive())


def test_an_empty_filter_hides_the_field() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.query_one("#filter").display
            await pilot.press("slash")
            assert app.query_one("#filter").has_focus
            await pilot.press("enter")
            assert not app.query_one("#filter").display
            assert [row[0] for row in rows(app)] == ["r1"]

    asyncio.run(drive())


def test_filtering_puts_the_cursor_on_the_first_row() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "slash", "r", "enter")
            table: Any = app.query_one("#runs")
            assert table.cursor_row == 0

    asyncio.run(drive())
