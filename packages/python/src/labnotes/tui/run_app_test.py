import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.run_app import RunApp

COLUMNS = ("run", "params", "status", "time", "memory", "size")
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
        mock.patch("labnotes.tui.run_app.SPINNER", "|"),
        mock.patch("labnotes.tui.run_app.signal", mock.Mock(SIGTERM=15, SIGHUP=1)),
        mock.patch("labnotes.tui.run_app.stop_then_kill") as stop_then_kill,
        mock.patch(
            "labnotes.tui.run_app.run_usage",
            new=mock.AsyncMock(
                side_effect=lambda folder, running: {
                    "memory": 3_200_000_000 if running else None,
                    "size": 5_000,
                }
            ),
        ) as run_usage,
    ):
        time.monotonic.return_value = 10.0
        yield {"time": time, "stop_then_kill": stop_then_kill, "run_usage": run_usage}


def rows(app: RunApp) -> list[list[str]]:
    table: Any = app.query_one("#runs")
    return [[str(cell) for cell in table.get_row(key)][:4] for key in table.rows]


def usage(app: RunApp) -> list[list[str]]:
    table: Any = app.query_one("#runs")
    return [[str(cell) for cell in table.get_row(key)][4:] for key in table.rows]


def began(run: str) -> dict[str, object]:
    return {
        "event": "started",
        "run": run,
        "params": {"m": run},
        "folder": f"/runs/{run}",
    }


def test_shows_what_each_run_uses(collaborators: dict[str, mock.MagicMock]) -> None:
    done = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        report(began("r1"))
        report(began("r2"))
        report({"event": "ended", "run": "r2", "exit_code": 0, "error": None})
        await done.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.tick()
            await pilot.pause()
            assert usage(app) == [["3.2 GB", "5.0 KB"], ["", "5.0 KB"], ["", ""]]
            assert app.query_one("#runs").ordered_columns[4].label.plain == "memory"  # type: ignore[attr-defined]
            assert app.query_one("#runs").ordered_columns[5].label.plain == "size"  # type: ignore[attr-defined]
            done.set()
            await pilot.pause()
            app.exit()

    asyncio.run(drive())
    calls = collaborators["run_usage"].await_args_list
    assert mock.call(Path("/runs/r2"), False) in calls
    assert mock.call(Path("/runs/r1"), True) in calls
    assert mock.call(Path("/runs/r2"), True) not in calls


def test_keeps_a_late_sample_off_a_run_that_ended(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    sampled = asyncio.Event()
    done = asyncio.Event()
    release = asyncio.Event()

    async def slow(folder: Path, running: bool) -> dict[str, int | None]:
        if running:
            sampled.set()
            await release.wait()
            return {"memory": 9_000, "size": 9_000}
        return {"memory": None, "size": 1_000}

    collaborators["run_usage"].side_effect = slow

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report(began("r1"))
        await sampled.wait()
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        await done.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.tick()
            await sampled.wait()
            await pilot.pause()
            release.set()
            await pilot.pause()
            assert usage(app) == [["", "1.0 KB"]]
            done.set()
            await pilot.pause()
            app.exit()

    asyncio.run(drive())


def test_waits_for_one_sample_before_taking_another(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    release = asyncio.Event()
    done = asyncio.Event()

    async def slow(folder: Path, running: bool) -> dict[str, int | None]:
        await release.wait()
        return {"memory": 2_000, "size": 3_000}

    collaborators["run_usage"].side_effect = slow

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report(began("r1"))
        await done.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.tick()
            app.tick()
            await pilot.pause()
            assert collaborators["run_usage"].await_count == 1
            release.set()
            await pilot.pause()
            assert usage(app) == [["2.0 KB", "3.0 KB"]]
            app.tick()
            await pilot.pause()
            assert collaborators["run_usage"].await_count == 2
            done.set()
            await pilot.pause()
            app.exit()

    asyncio.run(drive())


def test_shows_only_the_columns_it_is_given_in_their_order(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    done = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        report(began("r1"))
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        report(began("r2"))
        await done.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", ["size", "status", "run"])
        async with app.run_test() as pilot:
            await pilot.pause()
            app.tick()
            await pilot.pause()
            table: Any = app.query_one("#runs")
            assert [column.label.plain for column in table.ordered_columns] == [
                "size",
                "status",
                "run",
            ]
            assert [
                [str(cell) for cell in table.get_row(key)] for key in table.rows
            ] == [
                ["5.0 KB", "✓", "r1"],
                ["5.0 KB", "|", "r2"],
                ["", "○", "r3"],
            ]
            assert [getattr(cell, "style", None) for cell in table.get_row("r3")] == [
                "dim"
            ] * 3
            await pilot.press("slash", "m", "space", "r", "3", "enter")
            assert [str(table.get_row(key)[2]) for key in table.rows] == ["r3"]
            done.set()
            await pilot.pause()
            app.exit()

    asyncio.run(drive())


def styles(app: RunApp) -> list[list[object]]:
    table: Any = app.query_one("#runs")
    return [
        [getattr(cell, "style", None) for cell in table.get_row(key)][:4]
        for key in table.rows
    ]


def planned(*runs: str, mode: str = "matrix") -> dict[str, object]:
    return {
        "event": "planned",
        "title": "Exp",
        "runs": [{"run": run, "params": {"m": run}} for run in runs],
        "concurrency": 2,
        "mode": mode,
    }


def status(app: RunApp) -> str:
    widget: Any = app.query_one("#status")
    return str(widget.content)


def corner(app: RunApp) -> str:
    widget: Any = app.query_one("Header #concurrency")
    return str(widget.content)


def test_shows_each_run_and_the_outcome(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    finished = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(finish=finished.set))
        report(planned("r1", "r2", "r3"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        report(
            {
                "event": "started",
                "run": "r2",
                "params": {"m": "b"},
                "folder": "/runs/r2",
            }
        )
        collaborators["time"].monotonic.return_value = 34.0
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        report({"event": "ended", "run": "r2", "exit_code": None, "error": "boom"})
        report(
            {
                "event": "started",
                "run": "r3",
                "params": {"m": "c"},
                "folder": "/runs/r3",
            }
        )
        report({"event": "ended", "run": "r3", "exit_code": 1, "error": None})
        report({"event": "idle"})
        await finished.wait()
        return [
            {"exit_code": 0},
            {"exit_code": None},
            {"exit_code": 0},
            {"exit_code": 0},
        ]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.title == "Exp"
            assert rows(app) == [
                ["r1", "--m a", "✓", "24 seconds"],
                ["r2", "--m b", "✗ boom", "24 seconds"],
                ["r3", "--m c", "✗ exited 1", "0 seconds"],
            ]
            assert [row[2] for row in styles(app)] == ["", "red", "red"]
            assert status(app) == "1 passed, 2 failed. Ctrl-C to quit."
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not app.is_running
            assert len(app.results) == 4

    asyncio.run(drive())


def test_names_a_started_adhoc_run_without_its_invocation() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("inv/r1", "inv/r2"))
        report(
            {
                "event": "started",
                "run": "inv/r1",
                "params": {"m": "a"},
                "folder": "/runs/inv/r1",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[0] for row in rows(app)] == ["r1", "r2"]

    asyncio.run(drive())


def test_shows_planned_runs_as_dim_pending_rows() -> None:
    rendered = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        await rendered.wait()
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered.set()
            await pilot.pause()
            assert rows(app) == [
                ["r1", "--m a", "|", "0 seconds"],
                ["r2", "--m r2", "○", ""],
            ]
            assert styles(app) == [[None] * 4, ["dim"] * 4]
            table: Any = app.query_one("#runs")
            assert table.columns["time"].content_width == len("0 seconds")
            assert status(app) == ""

    asyncio.run(drive())


def test_skips_pending_runs_when_stopping() -> None:
    finished = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(finish=finished.set))
        report(planned("r1", "r2", "r3"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        report({"event": "stopping"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[2] for row in rows(app)] == ["|", "–", "–"]
            assert styles(app)[1][2] == "dim"
            assert status(app) == "said stopping"

    asyncio.run(drive())


def test_moves_queued_runs_up_the_pending_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3", "r4"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        report(
            {"event": "queued", "run": "r4", "pending": ["r4", "r2", "r3"], "held": []}
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[0] for row in rows(app)] == ["r1", "r4", "r2", "r3"]
            assert styles(app)[1] == ["dim"] * 4
            table: Any = app.query_one("#runs")
            assert table.cursor_row == 1
            assert status(app) == "said queued"

    asyncio.run(drive())


def test_clears_the_next_run_note_once_it_starts() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        report({"event": "queued", "run": "r3", "pending": ["r3", "r2"], "held": []})
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "said queued"
            run = "".join(["r", "3"])
            app.show_event(
                {
                    "event": "started",
                    "run": run,
                    "params": {"m": "c"},
                    "folder": "/runs",
                }
            )
            assert status(app) == ""

    asyncio.run(drive())


def test_keeps_later_notes_when_the_next_run_starts() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        report({"event": "queued", "run": "r2", "pending": ["r2"], "held": []})
        report({"event": "killing"})
        report(
            {
                "event": "started",
                "run": "r2",
                "params": {"m": "b"},
                "folder": "/runs/r2",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "said killing"

    asyncio.run(drive())


def test_moves_deselected_runs_to_the_bottom() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3", "r4"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
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
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[:3:2] for row in rows(app)] == [
                ["r1", "|"],
                ["r3", "–"],
                ["r4", "–"],
                ["r2", "⊘"],
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
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[:3:2] for row in rows(app)] == [
                ["r2", "–"],
                ["r3", "–"],
                ["r1", "–"],
            ]

    asyncio.run(drive())


def test_space_toggles_the_row_under_the_cursor() -> None:
    toggle = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(toggle=toggle))
        report(planned("r1", "r2"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "space")
            toggle.assert_called_once_with("r2")

    asyncio.run(drive())


def test_space_leaves_the_cursor_on_the_next_row() -> None:
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
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "space")
            await pilot.pause()
            table: Any = app.query_one("#runs")
            assert [row[0] for row in rows(app)] == ["r1", "r3", "r2"]
            assert table.cursor_row == 1

    asyncio.run(drive())


def test_space_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.press("space")
            controls.toggle.assert_not_called()

    asyncio.run(drive())


def test_n_runs_the_row_under_the_cursor_next() -> None:
    run_next = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(run_next=run_next))
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "n")
            run_next.assert_called_once_with("r3")

    asyncio.run(drive())


def test_n_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
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
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert corner(app) == "2 at a time"
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
        app = RunApp(start, "exp", COLUMNS)
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
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert (app.concurrency, corner(app)) == (5, "5 at a time")
            assert status(app) == ""

    asyncio.run(drive())


def test_shows_other_events_as_status() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report({"event": "killing"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "said killing"

    asyncio.run(drive())


def test_ticks_the_time_of_running_runs(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            collaborators["time"].monotonic.return_value = 25.0
            app.tick()
            assert rows(app) == [["r1", "--m a", "|", "15 seconds"]]

    asyncio.run(drive())


@mock.patch("labnotes.tui.run_app.SPINNER", "|/-\\")
def test_spins_the_status_of_running_runs() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch("labnotes.tui.run_app.DataTable.set_interval") as interval:
            async with app.run_test() as pilot:
                await pilot.pause()
                interval.assert_called_once_with(0.1, app.spin)
                spun = []
                for _ in range(4):
                    app.spin()
                    spun.append([row[2] for row in rows(app)])
                assert spun == [["/", "○"], ["-", "○"], ["\\", "○"], ["|", "○"]]

    asyncio.run(drive())


def started(*runs: str) -> list[dict[str, object]]:
    return [
        {"event": "started", "run": run, "params": {"m": run}, "folder": "/runs"}
        for run in runs
    ]


def going(controls: mock.Mock, *runs: str) -> Any:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(controls)
        report(planned(*runs))
        for event in started(*runs):
            report(event)
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    return start


def prompt(app: RunApp) -> str:
    widget: Any = app.screen.query_one("#prompt")
    return str(widget.content)


def test_ctrl_c_asks_before_leaving_runs_going() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1", "r2"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert prompt(app).startswith("2 runs still going.")
            await pilot.press("enter")
            await pilot.pause()
            assert not app.is_running
        assert controls.method_calls == []

    asyncio.run(drive())


def test_ctrl_q_asks_like_ctrl_c() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+q")
            await pilot.pause()
            assert prompt(app).startswith("1 run still going.")

    asyncio.run(drive())


def test_ctrl_c_twice_leaves_the_runs_going() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c", "ctrl+c")
            await pilot.pause()
            assert not app.is_running
        assert controls.method_calls == []

    asyncio.run(drive())


def test_s_at_the_prompt_stops_the_runs_then_kills_them() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        with mock.patch("labnotes.tui.run_app.GRACE_SECONDS", 0.3):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+c", "s")
                await pilot.pause()
                assert controls.interrupt.call_count == 1
                await asyncio.sleep(0.5)
                await pilot.pause()
                assert controls.interrupt.call_count == 2
                assert app.is_running
                assert not app.query("#prompt")

    asyncio.run(drive())


def test_escape_at_the_prompt_keeps_the_tui_open() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c", "escape")
            await pilot.pause()
            assert app.is_running
            assert not app.screen.query("#prompt")
            assert controls.method_calls == []

    asyncio.run(drive())


def test_table_keys_wait_while_the_prompt_is_open() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c", "x", "n", "j", "m")
            await pilot.pause()
            assert controls.method_calls == []
            assert app.screen.query("#prompt")

    asyncio.run(drive())


def test_ctrl_c_with_nothing_running_quits_and_leaves_the_queue_going() -> None:
    controls = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(controls)
        report(planned("r1"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.title == "Exp"
            await pilot.press("q")
            await pilot.pause()
            assert app.is_running
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not app.is_running
        assert controls.method_calls == []

    asyncio.run(drive())


def test_ctrl_c_finishes_once_idle() -> None:
    finished = asyncio.Event()
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        listen(mock.Mock(finish=finished.set))
        await finished.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            reports[0]({"event": "idle"})
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(drive())


def test_sigterm_stops_the_runs_then_finishes_once_idle(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            collaborators["stop_then_kill"].assert_called_once_with(app.stop_runs, 15)
            app.stop_runs()
            controls.interrupt.assert_called_once_with()
            app.show_event({"event": "idle"})
            app.stop_runs()
            controls.finish.assert_called_once_with()
            assert controls.interrupt.call_count == 1

    asyncio.run(drive())


def test_closing_the_terminal_leaves_the_runs_going() -> None:
    controls = mock.Mock()
    handlers: dict[object, Any] = {}

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        loop = asyncio.get_running_loop()
        with mock.patch.object(
            loop, "add_signal_handler", side_effect=handlers.__setitem__
        ):
            listen(controls)
        return await loop.create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert handlers == {1: app.exit}
            handlers[1]()
            await pilot.pause()
            assert not app.is_running
        assert controls.method_calls == []

    asyncio.run(drive())


def test_ticks_every_second_and_follows_output_often() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval") as set_interval:
            async with app.run_test() as pilot:
                await pilot.pause()
        assert set_interval.call_args_list == [
            mock.call(1, app.tick),
            mock.call(0.25, app.follow),
        ]

    asyncio.run(drive())


def test_widens_columns_as_cells_grow(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    rendered = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "a"},
                "folder": "/runs/r1",
            }
        )
        await rendered.wait()
        collaborators["time"].monotonic.return_value = 1234.0
        report({"event": "ended", "run": "r1", "exit_code": -15, "error": None})
        return [{"exit_code": -15}]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            rendered.set()
            await pilot.pause()
            table: Any = app.query_one("#runs")
            widths = [table.columns[key].content_width for key in ("status", "time")]
            assert widths == [len("✗ exited -15"), len("1224 seconds")]

    asyncio.run(drive())


def test_slash_filters_rows_by_params() -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash", "m", "space", "r", "2", "enter")
            assert [row[0] for row in rows(app)] == ["r2"]
            reports[0](
                {
                    "event": "started",
                    "run": "r1",
                    "params": {"m": "r1"},
                    "folder": "/runs/r1",
                }
            )
            reports[0](
                {
                    "event": "started",
                    "run": "r2",
                    "params": {"m": "r2"},
                    "folder": "/runs/r2",
                }
            )
            await pilot.pause()
            assert rows(app) == [["r2", "--m r2", "|", "0 seconds"]]
            assert app.query_one("#filter").display
            assert app.query_one("#runs").has_focus
            await pilot.press("escape")
            assert [row[:3] for row in rows(app)] == [
                ["r1", "--m r1", "|"],
                ["r2", "--m r2", "|"],
                ["r3", "--m r3", "○"],
            ]
            assert not app.query_one("#filter").display

    asyncio.run(drive())


def test_an_empty_filter_hides_the_field() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.query_one("#filter").display
            await pilot.press("slash")
            assert app.query_one("#filter").display
            assert app.query_one("#filter").has_focus
            await pilot.press("enter")
            assert not app.query_one("#filter").display
            assert [row[0] for row in rows(app)] == ["r1"]

    asyncio.run(drive())


def test_filtering_keeps_the_cursor_on_a_shown_row() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "slash", "r", "enter")
            table: Any = app.query_one("#runs")
            assert table.cursor_row == 2
            await pilot.press("slash", "1", "enter")
            assert table.cursor_row == 0

    asyncio.run(drive())


def test_shift_d_deselects_the_shown_pending_runs() -> None:
    toggle = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(toggle=toggle))
        report(planned("r1", "r2", "r3", "s1"))
        report(
            {
                "event": "started",
                "run": "r1",
                "params": {"m": "r1"},
                "folder": "/runs/r1",
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash", "r", "enter", "D")
            assert toggle.call_args_list == [mock.call("r2"), mock.call("r3")]

    asyncio.run(drive())


def test_x_stops_the_run_under_the_cursor() -> None:
    kill = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(kill=kill))
        report(planned("r1", "r2"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "x")
            kill.assert_called_once_with("r2")

    asyncio.run(drive())


def test_x_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.press("x")
            controls.kill.assert_not_called()

    asyncio.run(drive())


def test_f_hides_and_shows_failed_runs() -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned("r1", "r2", "r3"))
        for run in ("r1", "r2"):
            report(
                {
                    "event": "started",
                    "run": run,
                    "params": {"m": run},
                    "folder": "/runs",
                }
            )
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        report({"event": "ended", "run": "r2", "exit_code": 1, "error": None})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("f")
            assert [row[0] for row in rows(app)] == ["r1", "r3"]
            assert status(app) == "Failed runs hidden."
            reports[0](
                {
                    "event": "started",
                    "run": "r3",
                    "params": {"m": "r3"},
                    "folder": "/runs/r3",
                }
            )
            reports[0]({"event": "ended", "run": "r3", "exit_code": 2, "error": None})
            await pilot.pause()
            assert [row[0] for row in rows(app)] == ["r1"]
            await pilot.press("f")
            assert [row[0] for row in rows(app)] == ["r1", "r2", "r3"]
            assert status(app) == "Failed runs shown."

    asyncio.run(drive())


def test_r_retries_a_failed_run_as_a_new_pending_row() -> None:
    controls = mock.Mock()
    retry = controls.retry
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        listen(controls)
        report(planned("r1", "r2"))
        for run, code in (("r1", 0), ("r2", 1)):
            report(
                {
                    "event": "started",
                    "run": run,
                    "params": {"m": run},
                    "folder": "/runs",
                }
            )
            report({"event": "ended", "run": run, "exit_code": code, "error": None})
        report({"event": "idle"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "1 passed, 1 failed. Ctrl-C to quit."
            await pilot.press("r", "down", "r")
            retry.assert_called_once_with("r2")
            again = {"event": "retried", "run": "r2", "retry": "r3"}
            reports[0]({**again, "params": {"m": "r2"}})
            await pilot.pause()
            assert rows(app)[2] == ["r3", "--m r2", "○", ""]
            assert styles(app)[2][2] == "dim"
            assert status(app) == "said retried"
            reports[0](
                {
                    "event": "started",
                    "run": "r3",
                    "params": {"m": "r2"},
                    "folder": "/runs/r3",
                }
            )
            await pilot.press("ctrl+c", "enter")
            await pilot.pause()
            assert not app.is_running
            controls.finish.assert_not_called()

    asyncio.run(drive())


def test_r_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.press("r")
            controls.retry.assert_not_called()

    asyncio.run(drive())


def output(app: RunApp) -> list[str]:
    log: Any = app.query_one("#output")
    return [line.text.rstrip() for line in log.lines]


def test_enter_follows_the_output_of_the_run_under_the_cursor(
    tmp_path: Path,
) -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned("r1", "r2"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval"):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert not app.query_one("#output").display
                await pilot.press("down", "enter")
                assert app.query_one("#output").display
                assert not app.query_one("#runs").display
                assert (app.sub_title, status(app)) == ("r2", "")
                assert output(app) == []
                app.follow()
                assert output(app) == []
                (tmp_path / "stdout.log").write_text("hi\n")
                reports[0](
                    {
                        "event": "started",
                        "run": "r2",
                        "params": {"m": "r2"},
                        "folder": tmp_path,
                    }
                )
                app.follow()
                with (tmp_path / "stdout.log").open("a") as log:
                    log.write("more\n")
                app.follow()
                await pilot.pause()
                assert output(app) == ["hi", "more"]
                await pilot.press("escape")
                assert not app.query_one("#output").display
                assert app.query_one("#runs").display
                assert (app.sub_title, corner(app)) == ("", "2 at a time")

    asyncio.run(drive())


def test_only_back_and_quit_work_while_following_output() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter")
                actions = [binding.action for binding in RunApp.BINDINGS]  # type: ignore[union-attr]
                live = [action for action in actions if app.check_action(action, ())]
                assert live == ["interrupt", "leave"]
                assert app.check_action("command_palette", ())
                await pilot.press("n", "space", "x", "plus")
                controls.run_next.assert_not_called()
                controls.toggle.assert_not_called()
                controls.kill.assert_not_called()
                controls.set_concurrency.assert_not_called()
                await pilot.press("escape")
                assert app.check_action("run_next", ())
                await pilot.press("n")
                controls.run_next.assert_called_once_with("r1")

    asyncio.run(drive())


def test_starts_over_when_viewing_another_run(tmp_path: Path) -> None:
    for run, data in (("r1", b"old\n"), ("r2", b"hi\n")):
        (tmp_path / run).mkdir()
        (tmp_path / run / "stdout.log").write_bytes(data)

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        for run in ("r1", "r2"):
            report(
                {
                    "event": "started",
                    "run": run,
                    "params": {"m": run},
                    "folder": tmp_path / run,
                }
            )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval"):
            async with app.run_test() as pilot:
                await pilot.pause()
                app.view("r1")
                app.view("r2")
                await pilot.pause()
                assert output(app) == ["hi"]

    asyncio.run(drive())


def test_escape_brings_back_the_summary_once_idle() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report(
            {"event": "started", "run": "r1", "params": {"m": "r1"}, "folder": "/runs"}
        )
        report({"event": "ended", "run": "r1", "exit_code": 1, "error": None})
        report({"event": "idle"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval"):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter", "escape")
                assert status(app) == "0 passed, 1 failed. Ctrl-C to quit."

    asyncio.run(drive())


@pytest.mark.parametrize(
    ("runs", "mode", "viewing"),
    [
        (("r1",), "adhoc", "r1"),
        (("r1", "r2"), "adhoc", None),
        (("r1",), "matrix", None),
    ],
)
def test_opens_a_lone_adhoc_run_in_its_output(
    tmp_path: Path, runs: tuple[str, ...], mode: str, viewing: str | None
) -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned(*runs, mode=mode))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval"):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert app.viewing == viewing
                assert app.query_one("#output").display is (viewing is not None)
                if viewing is None:
                    return
                (tmp_path / "stdout.log").write_text("hi\n")
                reports[0](
                    {
                        "event": "started",
                        "run": "r1",
                        "params": {"m": "r1"},
                        "folder": tmp_path,
                    }
                )
                app.follow()
                assert output(app)[0] == "hi"
                await pilot.press("escape")
                assert [row[0] for row in rows(app)] == ["r1"]

    asyncio.run(drive())


def test_shows_nested_runs_by_their_own_name() -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned("g/r1", "g/r2"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            reports[0](
                {
                    "event": "retried",
                    "run": "g/r1",
                    "retry": "g/r3",
                    "params": {"m": "a"},
                }
            )
            await pilot.pause()
            assert [row[0] for row in rows(app)] == ["r1", "r2", "r3"]
            table: Any = app.query_one("#runs")
            assert [key.value for key in table.rows] == ["g/r1", "g/r2", "g/r3"]

    asyncio.run(drive())


@pytest.mark.parametrize(
    ("keys", "row"),
    [(("j",), 1), (("j", "j", "k"), 1), (("G",), 2), (("G", "g"), 0)],
)
def test_moves_the_cursor_with_vim_keys(keys: tuple[str, ...], row: int) -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press(*keys)
            table: Any = app.query_one("#runs")
            assert table.cursor_row == row

    asyncio.run(drive())


def test_keeps_the_error_that_stopped_the_runs() -> None:
    failure = ValueError("no daemon")

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        raise failure

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.is_running
            assert app.error is failure
            assert app.results == []

    asyncio.run(drive())


def test_has_no_error_when_the_runs_finish() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return [{"exit_code": 0}]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        assert app.error is None
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.is_running
            assert app.error is None
            assert app.results == [{"exit_code": 0}]

    asyncio.run(drive())


def grabbing(
    move: Callable[[str, int], None] | None = None,
) -> tuple[Callable[..., Any], list[Report], mock.Mock]:
    reports: list[Report] = []
    controls = mock.Mock()
    if move is not None:
        controls.move.side_effect = move

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        listen(controls)
        report(planned("r1", "r2", "r3", "r4"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}, "folder": "/r1"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    return start, reports, controls


def order(app: RunApp) -> list[object]:
    return [row[0] for row in rows(app)]


def cursor(app: RunApp) -> int:
    table: Any = app.query_one("#runs")
    return int(table.cursor_row)


def test_enter_drops_a_grabbed_run_where_j_moved_it() -> None:
    start, _, controls = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m")
            assert status(app) == (
                "Moving r2. j/k moves it, Enter drops it, Escape puts it back."
            )
            await pilot.press("j")
            assert order(app) == ["r1", "r3", "r2", "r4"]
            assert cursor(app) == 2
            await pilot.press("down")
            assert order(app) == ["r1", "r3", "r4", "r2"]
            assert cursor(app) == 3
            controls.move.assert_not_called()
            await pilot.press("enter")
            controls.move.assert_called_once_with("r2", 2)
            assert app.grabbed is None
            assert status(app) == ""
            assert app.query_one("#runs").display

    asyncio.run(drive())


def test_m_drops_a_grabbed_run_where_k_moved_it() -> None:
    start, _, controls = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("G", "m", "k", "up", "m")
            assert order(app) == ["r1", "r4", "r2", "r3"]
            controls.move.assert_called_once_with("r4", 0)

    asyncio.run(drive())


def test_a_grabbed_run_stays_inside_the_pending_runs() -> None:
    start, _, controls = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m", "k")
            assert (order(app), cursor(app)) == (["r1", "r2", "r3", "r4"], 1)
            await pilot.press("enter", "G", "m", "j")
            assert (order(app), cursor(app)) == (["r1", "r2", "r3", "r4"], 3)

    asyncio.run(drive())


def test_escape_puts_a_grabbed_run_back() -> None:
    start, _, controls = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m", "j", "j", "escape")
            assert (order(app), cursor(app)) == (["r1", "r2", "r3", "r4"], 1)
            assert status(app) == ""
            assert app.grabbed is None
            controls.move.assert_not_called()
            await pilot.press("j")
            assert cursor(app) == 2

    asyncio.run(drive())


def test_putting_back_keeps_runs_added_while_grabbed_last() -> None:
    start, reports, _ = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m", "j")
            reports[0](
                {"event": "retried", "run": "r1", "retry": "r5", "params": {"m": "e"}}
            )
            await pilot.press("escape")
            assert order(app) == ["r1", "r2", "r3", "r4", "r5"]

    asyncio.run(drive())


def test_only_pending_runs_can_be_grabbed() -> None:
    start, _, _ = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("m")
            assert app.grabbed is None
            await pilot.press("j")
            assert (order(app), cursor(app)) == (["r1", "r2", "r3", "r4"], 1)

    asyncio.run(drive())


def test_m_does_nothing_without_rows() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.press("m")
            assert app.grabbed is None

    asyncio.run(drive())


def test_only_grab_keys_work_while_grabbed() -> None:
    start, _, controls = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.check_action("shift", (1,))
            assert not app.check_action("drop", ())
            assert not app.check_action("put_back", ())
            await pilot.press("j", "m")
            actions = [binding.action for binding in RunApp.BINDINGS]  # type: ignore[union-attr]
            live = [action for action in actions if app.check_action(action, ())]
            assert live == ["interrupt", "grab", "drop", "put_back"]
            assert app.check_action("shift", (1,))
            assert app.check_action("command_palette", ())
            await pilot.press("n", "space", "x", "plus", "slash")
            assert controls.method_calls == []
            assert not app.query_one("#filter").display
            app.on_data_table_row_selected(mock.Mock())
            assert app.viewing is None

    asyncio.run(drive())


def test_a_grabbed_run_that_starts_goes_back_and_lets_go() -> None:
    start, reports, controls = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m", "j")
            run = "".join(["r", "2"])
            reports[0](
                {"event": "started", "run": run, "params": {"m": "b"}, "folder": "/"}
            )
            assert app.grabbed is None
            assert order(app) == ["r1", "r2", "r3", "r4"]
            await pilot.press("m")
            assert app.grabbed is None
            controls.move.assert_not_called()

    asyncio.run(drive())


def test_a_reorder_from_the_daemon_lets_go_of_the_grabbed_run() -> None:
    start, reports, _ = grabbing()

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m", "j")
            reports[0](
                {
                    "event": "queued",
                    "run": "r4",
                    "pending": ["r4", "r2", "r3"],
                    "held": [],
                }
            )
            assert app.grabbed is None
            assert order(app) == ["r1", "r4", "r2", "r3"]
            assert app.check_action("run_next", ())

    asyncio.run(drive())


def test_shows_where_the_daemon_moved_a_run() -> None:
    def move(run: str, place: int) -> None:
        reports[0](
            {"event": "moved", "run": run, "pending": ["r3", "r2", "r4"], "held": []}
        )

    start, reports, _ = grabbing(move)

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j", "m", "j", "enter")
            await pilot.pause()
            assert (order(app), cursor(app)) == (["r1", "r3", "r2", "r4"], 2)
            assert status(app) == "said moved"
            reports[0](
                {"event": "started", "run": "r3", "params": {"m": "c"}, "folder": "/"}
            )
            assert status(app) == "said moved"

    asyncio.run(drive())


def test_shows_log_blocks_above_the_output(tmp_path: Path) -> None:
    for run in ("r1", "r2"):
        (tmp_path / run).mkdir()
        (tmp_path / run / "stdout.log").write_text("raw\n")
    (tmp_path / "r1" / "log.jsonl").write_text('{"content": "answer"}\n')

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        for run in ("r1", "r2"):
            report(
                {
                    "event": "started",
                    "run": run,
                    "params": {"m": run},
                    "folder": tmp_path / run,
                }
            )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval"):
            async with app.run_test() as pilot:
                await pilot.pause()
                blocks = app.query_one("#blocks")
                assert not blocks.display
                app.view("r1")
                await pilot.pause()
                assert blocks.display
                assert [str(block.render()) for block in blocks.children] == [
                    "▸ answer"
                ]
                assert blocks.region.y < app.query_one("#output").region.y
                await pilot.press("escape")
                assert not blocks.display
                app.view("r2")
                await pilot.pause()
                assert not blocks.display
                assert list(blocks.children) == []

    asyncio.run(drive())


def test_shows_tempfail_retries_counting_down_then_their_outcome(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        listen(mock.Mock())
        report(planned("r1", "r3"))
        for run in ("r1", "r3"):
            report(
                {"event": "started", "run": run, "params": {"m": run}, "folder": "/"}
            )
            report({"event": "ended", "run": run, "exit_code": 75, "error": None})
            report({"event": "retrying", "run": run, "seconds": 30.0})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[2] for row in rows(app)] == [
                "✗ exited 75, retry in 30 seconds"
            ] * 2
            assert [row[2] for row in styles(app)] == ["yellow"] * 2
            assert status(app) == "said retrying"
            collaborators["time"].monotonic.return_value = 25.0
            app.tick()
            assert rows(app)[0][2] == "✗ exited 75, retry in 15 seconds"
            collaborators["time"].monotonic.return_value = 50.0
            app.tick()
            assert rows(app)[0][2] == "✗ exited 75, retry in 0 seconds"
            report = reports[0]
            report(
                {"event": "retried", "run": "r1", "retry": "r2", "params": {"m": "a"}}
            )
            report({"event": "retry cancelled", "run": "r3"})
            report(
                {"event": "started", "run": "r2", "params": {"m": "a"}, "folder": "/"}
            )
            report({"event": "ended", "run": "r2", "exit_code": 75, "error": None})
            report({"event": "gave up", "run": "r2", "retries": 2})
            assert status(app) == "said gave up"
            app.tick()
            assert [row[2] for row in rows(app)] == [
                "✗ exited 75, retried",
                "✗ exited 75",
                "✗ gave up (exit 75)",
            ]
            assert [row[2] for row in styles(app)] == ["red"] * 3
            report({"event": "idle"})
            assert status(app) == "0 passed, 2 failed. 1 retried. Ctrl-C to quit."
            await pilot.press("ctrl+c")

    asyncio.run(drive())


def test_a_manual_retry_keeps_the_runs_status() -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        listen(mock.Mock())
        report(planned("r1", "r2"))
        for run, code in (("r1", 1), ("r2", 0)):
            report(
                {"event": "started", "run": run, "params": {"m": run}, "folder": "/"}
            )
            report({"event": "ended", "run": run, "exit_code": code, "error": None})
        report({"event": "retried", "run": "r1", "retry": "r3", "params": {"m": "a"}})
        report({"event": "started", "run": "r3", "params": {"m": "a"}, "folder": "/"})
        report({"event": "ended", "run": "r3", "exit_code": 0, "error": None})
        report({"event": "idle"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[2] for row in rows(app)] == ["✗ exited 1", "✓", "✓"]
            assert status(app) == "2 passed, 0 failed. 1 retried. Ctrl-C to quit."
            await pilot.press("ctrl+c")

    asyncio.run(drive())


def test_a_retried_run_that_passed_counts_as_retried_not_failed() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock())
        report(planned("r1"))
        report({"event": "started", "run": "r1", "params": {"m": "a"}, "folder": "/"})
        report({"event": "ended", "run": "r1", "exit_code": 0, "error": None})
        report({"event": "retried", "run": "r1", "retry": "r2", "params": {"m": "a"}})
        report({"event": "started", "run": "r2", "params": {"m": "a"}, "folder": "/"})
        report({"event": "ended", "run": "r2", "exit_code": 0, "error": None})
        report({"event": "idle"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert status(app) == "1 passed, 0 failed. 1 retried. Ctrl-C to quit."
            await pilot.press("ctrl+c")

    asyncio.run(drive())
