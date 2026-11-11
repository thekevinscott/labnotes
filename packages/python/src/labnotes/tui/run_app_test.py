import asyncio
import json
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest

from labnotes.tui.run_app import NoMatches, RunApp, RunLiveView

COLUMNS = ("run", "params", "status", "time", "memory", "size")
Report = Callable[[dict[str, object]], None]
Listen = Callable[[Any], None]


def configured_app(
    tmp_path: Path, source: str | None, defaults: dict[str, object] | None = None
) -> RunApp:
    folder = tmp_path / "alpha"
    folder.mkdir(exist_ok=True)
    if source is not None:
        (folder / "experiment.toml").write_text(source)
    config = mock.Mock(
        root=tmp_path, experiments="{experiment}", defaults=defaults or {}
    )

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    return RunApp(start, "alpha", COLUMNS, config)


def test_configured_views_handles_missing_invalid_and_override_files(
    tmp_path: Path,
) -> None:
    defaults: dict[str, object] = {"views": {"progress": "progress.py:Progress"}}
    assert configured_app(tmp_path, None, defaults).view_specs == defaults["views"]
    assert configured_app(tmp_path, "[bad", defaults).view_specs == defaults["views"]
    override = tmp_path / "other.toml"
    override.write_text('command = "echo ok"\n[views]\ncustom = "custom.py:Custom"\n')
    app = configured_app(tmp_path, "[bad", defaults)
    app.experiment_config = override
    assert app.configured_views() == {"custom": "custom.py:Custom"}


def test_no_custom_views_mounts_builtin_without_opening_tables(tmp_path: Path) -> None:
    app = configured_app(tmp_path, 'command = "echo ok"\n[views]\nruns = "echo"\n')

    async def drive() -> None:
        with mock.patch("labnotes.tui.run_app.open_tables") as open_tables:
            async with app.run_test() as pilot:
                await pilot.pause()
                assert app.query_one(RunLiveView)
                open_tables.assert_not_called()

    asyncio.run(drive())


def test_custom_views_mount_in_pane_and_open_tables(tmp_path: Path) -> None:
    app = configured_app(
        tmp_path,
        'command = "echo ok"\ncontinues = false\n[views]\nprogress = "progress.py:Progress"\n',
    )

    async def changes():
        yield {"path": "alpha/runs/first/stdout.log"}

    async def reload():
        await asyncio.Event().wait()

    reloading = reload()

    async def drive() -> None:
        with (
            mock.patch("labnotes.tui.run_app.open_tables") as open_tables,
            mock.patch("labnotes.tui.run_app.watch_rows", return_value=changes()),
            mock.patch("labnotes.tui.run_app.reload_on_change", return_value=reloading),
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert app.query_one("#view-1")
                assert app.body_ready
                open_tables.assert_called_once_with(app.config, run_files=True)

    asyncio.run(drive())
    reloading.close()


def test_run_file_watcher_failure_keeps_shell_alive(tmp_path: Path) -> None:
    app = configured_app(
        tmp_path,
        'command = "echo ok"\n[views]\nprogress = "progress.py:Progress"\n',
    )
    failed = asyncio.Event()

    async def changes():
        yield {"path": "alpha/runs/first/stdout.log"}
        failed.set()
        raise RuntimeError("watch failed")

    async def reload():
        await asyncio.Event().wait()

    reloading = reload()

    async def drive() -> None:
        with (
            mock.patch("labnotes.tui.run_app.open_tables"),
            mock.patch("labnotes.tui.run_app.watch_rows", return_value=changes()),
            mock.patch("labnotes.tui.run_app.reload_on_change", return_value=reloading),
            mock.patch.object(app, "_handle_exception") as fatal,
        ):
            async with app.run_test() as pilot:
                await asyncio.wait_for(failed.wait(), timeout=2)
                await pilot.pause()
                assert app.query_one("#view-1")
                fatal.assert_not_called()

    asyncio.run(drive())
    reloading.close()


def test_builtin_pane_error_keeps_the_run_shell_alive(tmp_path: Path) -> None:
    app = configured_app(
        tmp_path,
        'command = "echo ok"\ncontinues = false\n[views]\nprogress = "progress.py:Progress"\n',
    )

    async def drive() -> None:
        with (
            mock.patch(
                "labnotes.tui.view_pane.load_view", side_effect=ImportError("broken")
            ),
            mock.patch("labnotes.tui.run_app.open_tables"),
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert not app.body_ready
                assert app.query_one("#view-1 .failure")
                app.listen(mock.Mock())
                app.show_event({"event": "planned"})
                app.stop_runs()
                app.action_interrupt()

    asyncio.run(drive())


def test_load_data_delivers_native_rows_and_skips_removed_experiment(
    tmp_path: Path,
) -> None:
    app = configured_app(tmp_path, None)
    loaded = {
        "views": {"progress": "progress.py:Progress"},
        "config": {"command": "go"},
    }

    async def drive() -> None:
        with (
            mock.patch(
                "labnotes.tui.run_app.load_experiment",
                new=mock.AsyncMock(return_value=None),
            ) as load,
            mock.patch(
                "labnotes.tui.run_app.native_rows", return_value=({"status": "passed"},)
            ),
            mock.patch.object(app, "add_views", new=mock.AsyncMock()) as add_views,
            mock.patch.object(app, "deliver") as deliver,
        ):
            await app.load_data(mock.Mock())
            assert not app.loaded_views
            load.return_value = loaded
            await app.load_data(mock.Mock())
            await app.load_data(mock.Mock())
            add_views.assert_awaited_once_with(loaded["views"], tmp_path)
            assert deliver.call_count == 2
            assert app.shown is not None
            assert app.shown.name == "alpha"
            assert app.shown.runs == ({"status": "passed"},)
            assert app.shown.config == {"command": "go"}

    asyncio.run(drive())


def test_run_file_change_notifies_view_and_escape_returns_to_runs(
    tmp_path: Path,
) -> None:
    app = configured_app(tmp_path, None)
    app.shown = mock.Mock()

    async def changes():
        yield {"path": "alpha/runs/first/stdout.log"}
        yield {"path": "alpha/runs/first/stderr.log"}

    with (
        mock.patch("labnotes.tui.run_app.watch_rows", return_value=changes()),
        mock.patch.object(app, "deliver") as deliver,
    ):
        asyncio.run(app.watch_files(mock.Mock()))
    assert deliver.call_args_list == [
        mock.call(app.shown, frozenset({"alpha/runs/first/stdout.log"})),
        mock.call(app.shown, frozenset({"alpha/runs/first/stderr.log"})),
    ]

    app.shown = None
    with (
        mock.patch("labnotes.tui.run_app.watch_rows", return_value=changes()),
        mock.patch.object(app, "deliver") as deliver,
    ):
        asyncio.run(app.watch_files(mock.Mock()))
    deliver.assert_not_called()

    with (
        mock.patch.object(app, "query_one", return_value=mock.Mock(current="view-2")),
        mock.patch.object(app, "action_show_view") as show,
    ):
        app.action_leave()
    show.assert_called_once_with(1)

    with (
        mock.patch.object(app, "query_one", return_value=mock.Mock(current="view-1")),
        mock.patch.object(app, "action_show_view") as show,
    ):
        app.action_leave()
    show.assert_not_called()


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
            app.body.tick()
            await pilot.pause()
            assert usage(app) == [["3.2 GB", "5.0 kB"], ["", "5.0 kB"], ["", ""]]
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
            app.body.tick()
            await sampled.wait()
            await pilot.pause()
            release.set()
            await pilot.pause()
            assert usage(app) == [["", "1.0 kB"]]
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
            app.body.tick()
            app.body.tick()
            await pilot.pause()
            assert collaborators["run_usage"].await_count == 1
            release.set()
            await pilot.pause()
            assert usage(app) == [["2.0 kB", "3.0 kB"]]
            app.body.tick()
            await pilot.pause()
            assert collaborators["run_usage"].await_count == 2
            done.set()
            await pilot.pause()
            app.exit()

    asyncio.run(drive())


def test_measures_runs_that_end_together_one_scan_at_a_time(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    sampled, release, done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    scanning = most = 0

    async def slow(folder: Path, running: bool) -> dict[str, int | None]:
        nonlocal scanning, most
        scanning += 1
        most = max(most, scanning)
        if running:
            sampled.set()
            await release.wait()
        await asyncio.sleep(0)
        scanning -= 1
        return {"memory": None, "size": 1_000}

    collaborators["run_usage"].side_effect = slow

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        for run in ("r1", "r2", "r3"):
            report(began(run))
        await sampled.wait()
        for run in ("r1", "r2", "r3"):
            report({"event": "ended", "run": run, "exit_code": 0, "error": None})
        await done.wait()
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.body.tick()
            await sampled.wait()
            await pilot.pause()
            release.set()
            for _ in range(5):
                await pilot.pause()
            assert usage(app) == [["", "1.0 kB"]] * 3
            done.set()
            await pilot.pause()
            app.exit()

    asyncio.run(drive())
    assert most == 1
    finals = [
        call.args[0]
        for call in collaborators["run_usage"].await_args_list
        if call.args[1] is False
    ]
    assert finals == [Path("/runs/r1"), Path("/runs/r2"), Path("/runs/r3")]


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
            app.body.tick()
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
                ["5.0 kB", "✓", "r1"],
                ["5.0 kB", "|", "r2"],
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


def planned(*runs: str) -> dict[str, object]:
    return {
        "event": "planned",
        "title": "Exp",
        "runs": [{"run": run, "params": {"m": run}} for run in runs],
        "concurrency": 2,
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


def test_finish_up_is_bound_to_f() -> None:
    bindings = [
        (binding.key, binding.description)  # type: ignore[union-attr]
        for binding in RunLiveView.BINDINGS
        if binding.action == "finish_up"  # type: ignore[union-attr]
    ]
    assert bindings == [("f", "Finish up")]


def test_finish_up_key_keeps_tui_open_and_skips_pending_runs() -> None:
    finish_up = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(finish_up=finish_up))
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
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            finish_up.assert_not_called()
            await pilot.press("f")
            await pilot.pause()
            finish_up.assert_called_once_with()
            assert app.is_running
            app.body.show_event({"event": "finishing up"})
            assert [row[2] for row in rows(app)] == ["|", "–"]
            assert status(app) == "said finishing up"

    asyncio.run(drive())


def test_in_process_tui_stays_open_after_finishing_up() -> None:
    finished_up = asyncio.Event()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(finish_up=finished_up.set))
        report(planned("r1", "r2"))
        await finished_up.wait()
        report({"event": "finishing up"})
        report({"event": "idle"})
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            assert app.is_running
            assert status(app).startswith("0 passed")
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(drive())


def test_earlier_event_does_not_mark_app_finishing_up() -> None:
    app = RunApp(None, "exp", COLUMNS)
    app.body_ready = False

    app.show_event({"event": "concurrency", "concurrency": 1})

    assert not app.finishing_up


def test_finishing_up_event_decoded_from_journal_marks_app_finishing_up() -> None:
    app = RunApp(None, "exp", COLUMNS)
    app.body_ready = False

    app.show_event(json.loads('{"event": "finishing up"}'))

    assert app.finishing_up


def test_plus_and_minus_change_the_concurrency() -> None:
    set_concurrency = mock.Mock()

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock(set_concurrency=set_concurrency))
        report(planned("r1", "r2"))
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
            assert (app.body.concurrency, corner(app)) == (5, "5 at a time")
            assert status(app) == ""

    asyncio.run(drive())


def test_passes_each_concurrency_event_time_to_the_label() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        report(json.loads('{"event": "concurrency", "concurrency": 3, "at": 7}'))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch(
            "labnotes.tui.flash_value.FlashValue.set_value", autospec=True
        ) as set_value:
            async with app.run_test() as pilot:
                await pilot.pause()
                label = app.query_one("Header #concurrency")
        assert set_value.call_args_list == [
            mock.call(label, "2 at a time", None),
            mock.call(label, "3 at a time", 7.0),
        ]
        assert type(set_value.call_args.args[2]) is float

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
            app.body.tick()
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
                interval.assert_called_once_with(0.1, app.body.spin)
                spun = []
                for _ in range(4):
                    app.body.spin()
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


def test_ctrl_c_asks_before_stopping_runs() -> None:
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
            assert app.is_running
        controls.interrupt.assert_called_once_with()

    asyncio.run(drive())


def test_detached_app_streams_and_routes_controls(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    journal = mock.Mock(path=tmp_path / "invocation.jsonl")
    journal.read.return_value = []
    app = RunApp(None, "exp", COLUMNS, config, daemon_journal=journal)

    async def drive() -> None:
        with (
            mock.patch.object(app, "attach_daemon") as attach,
            mock.patch.object(app, "queue_command") as queue,
            mock.patch.object(app, "drive", new=mock.AsyncMock()) as in_process,
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                attach.assert_called_once_with()
                in_process.assert_not_awaited()
                journal.read.assert_not_called()
                app.controls.set_concurrency(3)
                app.controls.kill("r1")
                app.controls.finish_up()
                assert queue.call_args_list == [
                    mock.call(
                        {
                            "command": "set_concurrency",
                            "count": 3,
                            "journal": str(journal.path),
                        }
                    ),
                    mock.call({"command": "stop_one", "run": "r1"}),
                    mock.call({"command": "finish_up"}),
                ]
                app.body.cells["r1"] = {"run": "r1"}
                app.body.folders["r1"] = tmp_path
                app.body.started["r1"] = 0.0
                await pilot.press("ctrl+c")
                await pilot.pause()
                assert "leave running" in prompt(app)
                await pilot.press("enter")
                await pilot.pause()
                assert not app.is_running

    asyncio.run(drive())


def test_detached_stop_waits_for_daemon_reply_before_exit(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    journal = mock.Mock(path=tmp_path / "invocation.jsonl")
    journal.read.return_value = []
    app = RunApp(None, "exp", COLUMNS, config, daemon_journal=journal)

    async def drive() -> None:
        with (
            mock.patch.object(app, "attach_daemon"),
            mock.patch(
                "labnotes.tui.run_app.daemon_command", return_value={"ok": True}
            ) as command,
        ):
            async with app.run_test() as pilot:
                app.body.cells["r1"] = {"run": "r1"}
                app.body.folders["r1"] = tmp_path
                app.body.started["r1"] = 0.0
                await pilot.press("ctrl+c", "s")
                await pilot.pause()
                command.assert_called_once_with(config, "exp", {"command": "stop_all"})
                assert not app.is_running

    asyncio.run(drive())


def test_detached_attach_replies_and_closes(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with (
        mock.patch(
            "labnotes.tui.run_app.daemon_socket", return_value=tmp_path / "run.sock"
        ),
        mock.patch("labnotes.tui.run_app.socket.socket") as socket_factory,
        mock.patch("labnotes.tui.run_app.socket.SocketIO") as socket_io,
    ):
        client = cast(mock.MagicMock, socket_factory.return_value)
        socket_io.return_value.__enter__.return_value.readline.return_value = (
            '{"ok":true,"journals":["/j1","/j2"]}\n'
        )
        assert app.attach_daemon() == ["/j1", "/j2"]
        assert app.attached is client
        client.connect.assert_called_once_with(str(tmp_path / "run.sock"))
        client.sendall.assert_called_once_with(b'{"command":"attach"}\n')
        socket_io.assert_called_once_with(client, "rb")
        app.on_unmount()
        client.close.assert_called_once_with()


def test_detached_attach_reports_missing_or_rejected_daemon(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with mock.patch("labnotes.tui.run_app.daemon_socket", return_value=None):
        with pytest.raises(ValueError, match="No daemon"):
            app.attach_daemon()
    with (
        mock.patch(
            "labnotes.tui.run_app.daemon_socket", return_value=tmp_path / "run.sock"
        ),
        mock.patch("labnotes.tui.run_app.socket.socket") as socket_factory,
        mock.patch("labnotes.tui.run_app.socket.SocketIO") as socket_io,
    ):
        client = cast(mock.MagicMock, socket_factory.return_value)
        socket_io.return_value.__enter__.return_value.readline.return_value = (
            '{"ok":false,"error":"busy"}\n'
        )
        with pytest.raises(ValueError, match="busy"):
            app.attach_daemon()
        client.close.assert_called_once_with()


def test_detached_command_errors_are_visible(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with (
        mock.patch(
            "labnotes.tui.run_app.daemon_command",
            return_value={"ok": False, "error": "cell gone"},
        ) as command,
        mock.patch.object(app.body, "show") as show,
    ):
        asyncio.run(app.send_command({"command": "stop_one", "run": "r1"}))
    command.assert_called_once_with(config, "exp", {"command": "stop_one", "run": "r1"})
    show.assert_called_once_with("cell gone")


def test_detached_restart_sends_run_id_and_reports_reply(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None,
        "exp",
        COLUMNS,
        config,
        tmp_path / "other.toml",
        daemon_journal=mock.Mock(path=tmp_path / "j", read=lambda: []),
    )
    with (
        mock.patch.object(app.body, "show") as show,
        mock.patch(
            "labnotes.tui.run_app.restart_request", return_value=mock.sentinel.request
        ) as request,
    ):
        app.restart_run("r1")
        show.assert_called_with("r1 has not failed.")
        app.body.failed.add("r1")
        with mock.patch.object(app, "run_worker") as worker:
            app.restart_run("r1")
            worker.assert_called_once()
            worker.call_args.args[0].close()
        with (
            mock.patch(
                "labnotes.tui.run_app.request_start",
                new=mock.AsyncMock(return_value={"journal": str(tmp_path / "r.jsonl")}),
            ) as command,
        ):
            asyncio.run(app.restart_daemon_run("r1"))
            request.assert_called_once_with("r1", tmp_path / "other.toml")
            assert command.call_args.args[:3] == (config, "exp", mock.sentinel.request)
            show.assert_called_with("Restarted r1.")
            command.call_args.args[3]("Preparing codebase")
            show.assert_called_with("Restarting r1: Preparing codebase")
        with mock.patch(
            "labnotes.tui.run_app.request_start",
            new=mock.AsyncMock(side_effect=ValueError("locked")),
        ):
            asyncio.run(app.restart_daemon_run("r1"))
            show.assert_called_with("Could not restart r1: locked")


def test_detached_startup_error_is_reported(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    journal = mock.Mock(path=tmp_path / "j")
    app = RunApp(None, "exp", COLUMNS, config, daemon_journal=journal)

    async def drive() -> None:
        with mock.patch.object(app, "attach_daemon", side_effect=ValueError("gone")):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert isinstance(app.error, ValueError)
                assert str(app.error) == "gone"

    asyncio.run(drive())


def test_detached_ctrl_c_quits_quietly_only_once_the_invocation_is_done(
    tmp_path: Path,
) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with (
        mock.patch.object(app, "exit") as exit_app,
        mock.patch.object(app, "push_screen") as prompt_screen,
        mock.patch.object(app.body, "busy", return_value=None),
    ):
        app.action_interrupt()
        exit_app.assert_called_once_with()
        prompt_screen.assert_not_called()


@pytest.mark.parametrize(
    ("ready", "busy", "shown"),
    [
        (True, "Setting up.", "Setting up."),
        (False, None, "Still running."),
    ],
)
def test_detached_ctrl_c_asks_while_the_invocation_is_busy(
    tmp_path: Path, ready: bool, busy: str | None, shown: str
) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    app.body_ready = ready
    with (
        mock.patch.object(app, "exit") as exit_app,
        mock.patch.object(app, "push_screen") as prompt_screen,
        mock.patch.object(app.body, "busy", return_value=busy),
    ):
        app.action_interrupt()
        exit_app.assert_not_called()
        [(screen, answer)] = [call.args for call in prompt_screen.call_args_list]
        assert screen.busy == shown
        assert answer == app.answer


def test_detached_leave_names_the_attach_and_stop_commands(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with mock.patch.object(app, "exit") as exit_app:
        app.answer("leave")
        exit_app.assert_called_once_with()
    assert app.farewell == (
        "exp is still running.\n"
        "Reattach with: labnotes experiments exp attach\n"
        "Stop it with: labnotes experiments exp stop"
    )


def test_detached_restart_binding_selects_row(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with (
        mock.patch.object(
            type(app.body), "app", new_callable=mock.PropertyMock, return_value=app
        ),
        mock.patch.object(app.body, "cursor_run", return_value="r1"),
        mock.patch.object(app, "restart_run") as restart,
    ):
        app.body.action_restart_run()
        restart.assert_called_once_with("r1")
        restart.reset_mock()
        with mock.patch.object(app.body, "cursor_run", return_value=None):
            app.body.action_restart_run()
        restart.assert_not_called()


def test_detached_queue_command_starts_worker(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    with mock.patch.object(app, "run_worker") as worker:
        app.queue_command({"command": "stop_all"})
        worker.assert_called_once_with(mock.ANY, exit_on_error=False)
        worker.call_args.args[0].close()


def test_detached_command_error_with_unavailable_view_is_safe(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(
        None, "exp", COLUMNS, config, daemon_journal=mock.Mock(path=tmp_path / "j")
    )
    app.body_ready = False
    with (
        mock.patch(
            "labnotes.tui.run_app.daemon_command", side_effect=ValueError("gone")
        ),
        mock.patch.object(app.body, "show") as show,
    ):
        asyncio.run(app.send_command({"command": "stop_all"}))
    show.assert_not_called()


def test_restart_binding_ignores_foreground_mode(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(mock.AsyncMock(), "exp", COLUMNS, config)
    with mock.patch.object(app, "run_worker") as worker:
        app.restart_run("r1")
        worker.assert_not_called()


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


def test_ctrl_c_twice_stops_the_runs() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+c", "ctrl+c")
            await pilot.pause()
            assert app.is_running
        controls.interrupt.assert_called_once_with()

    asyncio.run(drive())


def test_s_at_the_prompt_stops_the_runs_then_kills_them() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        with mock.patch.object(app, "set_timer") as set_timer:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+c", "s")
                await pilot.pause()
                controls.interrupt.assert_called_once_with()
                set_timer.assert_called_once()
                set_timer.call_args.args[1]()
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
            await pilot.press("ctrl+c", "x", "j")
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
            assert collaborators["stop_then_kill"].call_args_list == [
                mock.call(app.stop_runs, 15),
                mock.call(app.stop_runs, 1),
            ]
            app.stop_runs()
            controls.interrupt.assert_called_once_with()
            app.show_event({"event": "idle"})
            app.stop_runs()
            controls.finish.assert_called_once_with()
            assert controls.interrupt.call_count == 1

    asyncio.run(drive())


def test_sighup_stops_the_runs() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls, "r1"), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.stop_runs()
            controls.interrupt.assert_called_once_with()

    asyncio.run(drive())


def test_signal_exits_an_idle_in_process_tui_after_finish_up() -> None:
    controls = mock.Mock()

    async def drive() -> None:
        app = RunApp(going(controls), "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.show_event({"event": "finishing up"})
            app.show_event({"event": "idle"})
            with mock.patch.object(app, "exit") as exit_app:
                app.stop_runs()
            exit_app.assert_called_once_with()
            controls.finish.assert_not_called()
            controls.interrupt.assert_not_called()

    asyncio.run(drive())


def test_ticks_every_second_and_follows_output_often() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        return []

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app.body, "set_interval") as set_interval:
            async with app.run_test() as pilot:
                await pilot.pause()
        assert set_interval.call_args_list == [
            mock.call(1, app.body.tick),
            mock.call(0.25, app.body.follow),
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


def test_numbers_shown_rows_from_one() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2", "r3"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            table: Any = app.query_one("#runs")
            labels = [str(row.label) for row in table.ordered_rows]
            assert labels == ["1", "2", "3"]
            await pilot.press("slash", "m", "space", "r", "2", "enter")
            labels = [str(row.label) for row in table.ordered_rows]
            assert labels == ["1"]

    asyncio.run(drive())


def test_an_empty_filter_hides_the_field() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
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
            assert [row[0] for row in rows(app)] == ["r1", "r2"]

    asyncio.run(drive())


def test_escape_shows_on_the_table_only_with_the_filter_open() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1", "r2"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not app.body.check_action("leave", ())
            await pilot.press("slash")
            assert app.body.check_action("leave", ())
            await pilot.press("r", "enter")
            assert app.body.check_action("leave", ())
            await pilot.press("escape")
            assert not app.body.check_action("leave", ())
            await pilot.press("enter")
            assert app.body.check_action("leave", ())

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
        with mock.patch.object(app.body, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.press("x")
            controls.kill.assert_not_called()

    asyncio.run(drive())


def stdout_log(app: RunApp, selector: str) -> Any:
    output: Any = app.query_one(selector)
    return output.logs["stdout"]


def output(app: RunApp) -> list[str]:
    log = stdout_log(app, "#output")
    return [line.rstrip() for line in log.read(0, log.rows)]


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
                app.body.follow()
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
                app.body.follow()
                with (tmp_path / "stdout.log").open("a") as log:
                    log.write("more\n")
                app.body.follow()
                await pilot.pause()
                assert output(app) == ["hi", "more"]
                await pilot.press("escape")
                assert not app.query_one("#output").display
                assert app.query_one("#runs").display
                assert (app.sub_title, corner(app)) == ("", "2 at a time")

    asyncio.run(drive())


def test_back_quit_and_finish_up_work_while_following_output() -> None:
    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r1"))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app.body, "controls") as controls:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter")
                actions = [binding.action for binding in RunLiveView.BINDINGS]  # type: ignore[union-attr]
                live = [
                    action
                    for action in ["interrupt", *actions]
                    if app.body.check_action(action, ())
                ]
                assert live == ["interrupt", "finish_up", "leave"]
                assert app.body.check_action("command_palette", ())
                await pilot.press("f")
                controls.finish_up.assert_called_once_with()
                await pilot.press("x", "plus")
                controls.kill.assert_not_called()
                controls.set_concurrency.assert_not_called()
                await pilot.press("escape")
                assert app.body.check_action("kill_run", ())
                await pilot.press("x")
                controls.kill.assert_called_once_with("r1")

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
                app.body.view("r1")
                app.body.view("r2")
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


@pytest.mark.parametrize(("runs", "viewing"), [(("r1",), "r1"), (("r1", "r2"), None)])
def test_opens_a_lone_run_in_its_output(
    tmp_path: Path, runs: tuple[str, ...], viewing: str | None
) -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        report(planned(*runs))
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        with mock.patch.object(app, "set_interval"):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert app.body.viewing == viewing
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
                app.body.follow()
                assert output(app)[0] == "hi"
                await pilot.press("escape")
                assert [row[0] for row in rows(app)] == ["r1"]

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
                app.body.view("r1")
                await pilot.pause()
                assert blocks.display
                assert [str(block.render()) for block in blocks.children] == [
                    "▸ answer"
                ]
                assert blocks.region.y < app.query_one("#output").region.y
                await pilot.press("escape")
                assert not blocks.display
                app.body.view("r2")
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
            app.body.tick()
            assert rows(app)[0][2] == "✗ exited 75, retry in 15 seconds"
            collaborators["time"].monotonic.return_value = 50.0
            app.body.tick()
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
            app.body.tick()
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


def test_a_run_retried_in_its_own_folder_counts_once() -> None:
    A = {"m": "a"}

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        listen(mock.Mock())
        report(planned("r1"))
        for code in (75, 0):
            report(
                {"event": "started", "run": "r1", "params": {"m": "a"}, "folder": "/"}
            )
            report({"event": "ended", "run": "r1", "exit_code": code, "error": None})
            if code:
                report({"event": "retried", "run": "r1", "retry": "r1", "params": A})
        report({"event": "idle"})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert [row[2] for row in rows(app)] == ["✓"]
            assert status(app) == "1 passed, 0 failed. Ctrl-C to quit."
            await pilot.press("ctrl+c")

    asyncio.run(drive())


@pytest.mark.parametrize(
    ("run", "retry", "same_run"),
    [
        ("r2", "r1", False),
        ("".join(["r", "2"]), "".join(["r2", ""]), True),
    ],
)
def test_retried_run_ids_use_value_equality(
    run: str, retry: str, same_run: bool
) -> None:
    if same_run:
        assert run is not retry

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("r2", "other"))
        report({"event": "retried", "run": run, "retry": retry, "params": {}})
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert ("r2" in app.body.retried) is not same_run
            await pilot.press("ctrl+c")

    asyncio.run(drive())


def test_live_app_delivers_events_directly_without_polling() -> None:
    app = RunApp(None, "exp", COLUMNS)
    event: dict[str, object] = {"event": "planned", "runs": []}
    with (
        mock.patch.object(app, "set_interval") as interval,
        mock.patch.object(app.body, "show_event") as show,
    ):
        app.show_event(event)
        show.assert_called_once_with(event)
        interval.assert_not_called()
        app.body_ready = False
        app.show_event(event)
        show.assert_called_once_with(event)


@pytest.mark.parametrize(
    ("started_at", "retry_at", "expected_started", "expected_retry"),
    [(990.0, 1020.0, 90.0, 120.0), (1005.0, 995.0, 100.0, 100.0)],
)
def test_replayed_wall_times_keep_elapsed_and_retry_countdown(
    collaborators: dict[str, Any],
    started_at: float,
    retry_at: float,
    expected_started: float,
    expected_retry: float,
) -> None:
    clock = collaborators["time"]
    clock.monotonic.return_value = 100.0
    clock.time.return_value = 1000.0

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        report(planned("running", "waiting"))
        report(
            {
                "event": "started",
                "run": "running",
                "params": {"m": "a"},
                "folder": "/",
                "at": started_at,
            }
        )
        report(
            {
                "event": "retrying",
                "run": "waiting",
                "seconds": 30.0,
                "retry_at": retry_at,
            }
        )
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.body.started["running"] == expected_started
            assert app.body.waiting["waiting"] == expected_retry
            await pilot.press("ctrl+c")

    asyncio.run(drive())


def hooked(*hooks: str) -> dict[str, object]:
    return {**planned("r1", "r2"), "hooks": list(hooks)}


def stage(app: RunApp) -> str:
    return app.query_one(RunLiveView).stage


def shown_stages(app: RunApp) -> str:
    widget: Any = app.query_one("#stages")
    return str(widget.content) if widget.display else ""


def drive_hooks(steps: Callable[[RunApp, Any, Report], Awaitable[None]]) -> None:
    reports: list[Report] = []

    async def start(report: Report, listen: Listen) -> list[dict[str, object]]:
        reports.append(report)
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "exp", COLUMNS)
        async with app.run_test() as pilot:
            await pilot.pause()
            await steps(app, pilot, reports[0])

    asyncio.run(drive())


def test_shows_no_stages_without_hooks() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(planned("r1", "r2"))
        await pilot.pause()
        assert shown_stages(app) == ""
        assert stage(app) == "runs"
        await pilot.press("left_square_bracket")
        assert stage(app) == "runs"

    drive_hooks(steps)


def test_opens_on_setup_then_advances_to_runs_and_teardown(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup", "teardown"))
        await pilot.pause()
        assert stage(app) == "setup"
        assert "setup" in shown_stages(app) and "teardown" in shown_stages(app)
        report({"event": "setting up", "hook": "setup", "folder": tmp_path / "s"})
        report({"event": "hook ended", "hook": "setup", "error": None})
        await pilot.pause()
        assert stage(app) == "runs"
        assert "setup ✓" in shown_stages(app)
        report({"event": "tearing down", "hook": "teardown", "folder": tmp_path})
        await pilot.pause()
        assert stage(app) == "teardown"
        report({"event": "hook ended", "hook": "teardown", "error": None})
        await pilot.pause()
        assert stage(app) == "teardown"

    drive_hooks(steps)


def test_stays_on_a_failed_setup(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup"))
        report({"event": "setting up", "hook": "setup", "folder": tmp_path})
        report({"event": "hook ended", "hook": "setup", "error": "up broke"})
        await pilot.pause()
        assert stage(app) == "setup"
        assert "setup ✗" in shown_stages(app)

    drive_hooks(steps)


def test_moving_by_hand_stops_auto_advance(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup", "teardown"))
        report({"event": "setting up", "hook": "setup", "folder": tmp_path})
        await pilot.pause()
        await pilot.press("right_square_bracket", "right_square_bracket")
        assert stage(app) == "teardown"
        await pilot.press("left_square_bracket", "left_square_bracket")
        assert stage(app) == "setup"
        await pilot.press("left_square_bracket")
        assert stage(app) == "setup"
        report({"event": "hook ended", "hook": "setup", "error": None})
        report({"event": "tearing down", "hook": "teardown", "folder": tmp_path})
        await pilot.pause()
        assert stage(app) == "setup"

    drive_hooks(steps)


def test_run_keys_do_nothing_off_the_runs_stage(tmp_path: Path) -> None:
    kill = mock.Mock()

    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        app.query_one(RunLiveView).controls = mock.Mock(kill=kill)
        report(hooked("setup"))
        await pilot.pause()
        await pilot.press("x", "slash")
        kill.assert_not_called()
        assert not app.query_one("#filter").display

    drive_hooks(steps)


def test_keeps_the_summary_after_teardown(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("teardown"))
        report({"event": "idle"})
        report({"event": "tearing down", "hook": "teardown", "folder": tmp_path})
        report({"event": "hook ended", "hook": "teardown", "error": None})
        await pilot.pause()
        assert status(app) == "0 passed, 0 failed. Ctrl-C to quit."

    drive_hooks(steps)


def test_busy_names_the_phase_until_runs_end_without_hooks() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        busy = app.query_one(RunLiveView).busy
        assert busy() == "Starting runs."
        report(planned("r1", "r2"))
        assert busy() == "Starting runs."
        report(started("r1")[0])
        assert busy() == "1 run still going."
        report(started("r2")[0])
        assert busy() == "2 runs still going."
        for run in ("r1", "r2"):
            report({"event": "ended", "run": run, "error": None, "exit_code": 75})
            report({"event": "retrying", "run": run, "seconds": 60})
        assert busy() == "2 runs waiting to retry."
        report({"event": "retry cancelled", "run": "r1"})
        assert busy() == "1 run waiting to retry."
        report({"event": "idle"})
        assert busy() is None

    drive_hooks(steps)


@pytest.mark.parametrize("error", [None, "down broke"])
def test_busy_names_the_phase_until_teardown_ends(
    tmp_path: Path, error: str | None
) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        busy = app.query_one(RunLiveView).busy
        report(hooked("setup", "teardown"))
        assert busy() == "Starting runs."
        report({"event": "setting up", "hook": "setup", "folder": tmp_path / "s"})
        assert busy() == "Setting up."
        report({"event": "hook ended", "hook": "setup", "error": None})
        assert busy() == "Starting runs."
        report({"event": "idle"})
        assert busy() == "Tearing down."
        report({"event": "tearing down", "hook": "teardown", "folder": tmp_path})
        assert busy() == "Tearing down."
        report({"event": "hook ended", "hook": "teardown", "error": error})
        assert busy() is None

    drive_hooks(steps)


@pytest.mark.parametrize(
    ("hooks", "busy"), [(("setup",), None), (("setup", "teardown"), "Tearing down.")]
)
def test_busy_after_a_failed_setup_waits_only_for_teardown(
    tmp_path: Path, hooks: tuple[str, ...], busy: str | None
) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked(*hooks))
        report({"event": "setting up", "hook": "setup", "folder": tmp_path})
        report({"event": "hook ended", "hook": "setup", "error": "up broke"})
        assert app.query_one(RunLiveView).busy() == busy

    drive_hooks(steps)


def hook_calls(app: RunApp, method: str) -> dict[str, bool]:
    view = app.query_one(RunLiveView)
    panels = {hook: app.query_one(f"#{hook}-stage") for hook in ("setup", "teardown")}
    with (
        mock.patch.object(panels["setup"], method) as setup,
        mock.patch.object(panels["teardown"], method) as teardown,
    ):
        getattr(view, method)()
    return {"setup": setup.called, "teardown": teardown.called}


def test_ticks_and_follows_only_the_running_hook(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup", "teardown"))
        report({"event": "setting up", "hook": "setup", "folder": tmp_path})
        await pilot.pause()
        running = {"setup": True, "teardown": False}
        assert hook_calls(app, "tick") == running
        assert hook_calls(app, "follow") == running
        report({"event": "hook ended", "hook": "setup", "error": None})
        report({"event": "tearing down", "hook": "teardown", "folder": tmp_path})
        await pilot.pause()
        running = {"setup": False, "teardown": True}
        assert hook_calls(app, "tick") == running
        assert hook_calls(app, "follow") == running

    drive_hooks(steps)


def displayed(app: RunApp) -> list[str]:
    names = ("setup", "runs", "teardown")
    return [name for name in names if app.query_one(f"#{name}-stage").display]


def test_shows_only_the_current_stage_for_decoded_hooks(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report({**planned("r1", "r2"), "hooks": json.loads('["setup", "teardown"]')})
        await pilot.pause()
        assert displayed(app) == ["setup"]
        await pilot.press("right_square_bracket")
        assert displayed(app) == ["runs"]
        await pilot.press("right_square_bracket")
        assert displayed(app) == ["teardown"]

    drive_hooks(steps)


def test_a_single_run_opens_its_output_once_setup_passes(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report({**planned("r1"), "hooks": ["setup"]})
        report({"event": "setting up", "hook": "setup", "folder": tmp_path})
        await pilot.pause()
        assert app.focused is stdout_log(app, "#setup-output")
        report({"event": "hook ended", "hook": "setup", "error": None})
        await pilot.pause()
        assert displayed(app) == ["runs"]
        assert app.focused is stdout_log(app, "#output")

    drive_hooks(steps)


def test_stops_at_the_last_stage() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup"))
        await pilot.pause()
        await pilot.press("right_square_bracket", "right_square_bracket")
        assert stage(app) == "runs"

    drive_hooks(steps)


def test_stage_keys_are_bound_only_with_hooks() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(planned("r1", "r2"))
        await pilot.pause()
        assert "left_square_bracket" not in app.screen.active_bindings
        report(hooked("setup"))
        await pilot.pause()
        assert "left_square_bracket" in app.screen.active_bindings

    drive_hooks(steps)


def test_shows_a_finished_setup_while_runs_continue(tmp_path: Path) -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup"))
        report({"event": "setting up", "hook": "setup", "folder": tmp_path})
        report({"event": "hook ended", "hook": "setup", "error": None})
        await pilot.pause()
        assert status(app) == "said hook ended"

    drive_hooks(steps)


def test_a_hook_that_never_started_does_not_advance() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(hooked("setup"))
        report({"event": "hook ended", "hook": "setup", "error": None})
        await pilot.pause()
        assert stage(app) == "setup"

    drive_hooks(steps)


@pytest.mark.parametrize(
    ("idle", "started", "ended", "failed", "retried", "state"),
    [
        (False, {}, set(), set(), set(), "waiting"),
        (False, {"r1": 0.0}, set(), set(), set(), "running"),
        (False, {}, {"r1"}, set(), set(), "running"),
        (True, {}, {"r1"}, {"r1"}, set(), "failed"),
        (True, {}, {"r1", "r2"}, {"r1"}, {"r1"}, "passed"),
        (True, {}, {"r1", "r2"}, set(), {"r1"}, "passed"),
        (True, {}, {"r1"}, set(), set(), "passed"),
    ],
    ids=[
        "nothing-started",
        "one-running",
        "one-ended",
        "a-failure",
        "a-failure-retried",
        "a-retried-run-restarted-and-passed",
        "all-passed",
    ],
)
def test_runs_stage_state(
    idle: bool,
    started: dict[str, float],
    ended: set[str],
    failed: set[str],
    retried: set[str],
    state: str,
) -> None:
    view = RunLiveView()
    view.idle, view.started, view.ended = idle, started, ended
    view.failed, view.retried = failed, retried

    assert view.stage_state("runs") == state


def starting_app(tmp_path: Path) -> RunApp:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    return RunApp(None, "exp", COLUMNS, config, daemon_request={"command": "start"})


@pytest.mark.parametrize("body_ready", [True, False])
def test_startup_shows_each_step_then_follows_the_run(
    tmp_path: Path, body_ready: bool
) -> None:
    app = starting_app(tmp_path)
    accept = asyncio.Event()

    async def request_start(config, name, request, progress):
        progress("Starting daemon")
        progress("Snapshotting repo")
        await accept.wait()
        return {"ok": True, "journal": str(tmp_path / "j.jsonl")}

    async def drive() -> None:
        with (
            mock.patch("labnotes.tui.run_app.ensure_daemon", new=mock.AsyncMock()),
            mock.patch.object(app, "attach_daemon"),
            mock.patch("labnotes.tui.run_app.request_start", new=request_start),
            mock.patch.object(app, "follow_daemon") as follow,
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                shown = str(app.query_one("#startup").render())
                assert "✓ Starting daemon" in shown
                assert "Snapshotting repo" in shown
                assert app.query_one("#startup").display is True
                assert app.query_one("ContentSwitcher").display is False
                app.body_ready = body_ready
                with (
                    mock.patch.object(app.body, "go", wraps=app.body.go) as go,
                    mock.patch.object(
                        app.screen, "focus_next", wraps=app.screen.focus_next
                    ) as focus_next,
                ):
                    accept.set()
                    await pilot.pause()
                    await pilot.pause()
                follow.assert_called_once_with()
                assert app.daemon_journal is not None
                assert app.daemon_journal.path == tmp_path / "j.jsonl"
                assert app.query_one("#startup").display is False
                await pilot.pause()
                assert app.focused is not None
                if body_ready:
                    go.assert_called_once_with(app.body.stage)
                    focus_next.assert_not_called()
                    assert app.focused is app.body.query_one("DataTable")
                else:
                    focus_next.assert_called_once_with()
                    go.assert_not_called()
                    assert app.focused is app.screen.focus_chain[0]

    asyncio.run(drive())


def test_a_setup_plan_streamed_while_starting_keeps_the_setup_stage(
    tmp_path: Path,
) -> None:
    app = starting_app(tmp_path)
    journal = str(tmp_path / "j.jsonl")

    async def request_start(config, name, request, progress):
        return {"ok": True, "journal": journal}

    def stream_arrives() -> None:
        app.call_later(
            app.forward, journal, {**planned("r1", "r2"), "hooks": ["setup"]}
        )

    async def drive() -> None:
        with (
            mock.patch("labnotes.tui.run_app.ensure_daemon", new=mock.AsyncMock()),
            mock.patch.object(app, "attach_daemon"),
            mock.patch("labnotes.tui.run_app.request_start", new=request_start),
            mock.patch.object(app, "follow_daemon", side_effect=stream_arrives),
        ):
            async with app.run_test() as pilot:
                for _ in range(5):
                    await pilot.pause()
                assert app.body.stage == "setup"
                assert app.body.query_one("#setup-stage").display is True
                assert app.body.query_one("#runs-stage").display is False

    asyncio.run(drive())


def test_startup_failure_exits_with_the_error(tmp_path: Path) -> None:
    app = starting_app(tmp_path)

    async def request_start(config, name, request, progress):
        progress("Starting daemon")
        raise OSError("AF_UNIX path too long")

    async def drive() -> None:
        with (
            mock.patch("labnotes.tui.run_app.ensure_daemon", new=mock.AsyncMock()),
            mock.patch.object(app, "attach_daemon"),
            mock.patch("labnotes.tui.run_app.request_start", new=request_start),
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert not app.is_running
        assert isinstance(app.error, ValueError)
        assert str(app.error) == "AF_UNIX path too long"

    asyncio.run(drive())


def test_ctrl_c_before_the_daemon_replies_names_the_stop_command(
    tmp_path: Path,
) -> None:
    app = starting_app(tmp_path)
    with mock.patch.object(app, "exit") as exit_app:
        app.action_interrupt()
        exit_app.assert_called_once_with()
    assert app.farewell == (
        "exp may still start. Stop it with: labnotes experiments exp stop"
    )


def test_startup_spinner_ticks_ten_times_a_second(tmp_path: Path) -> None:
    app = starting_app(tmp_path)

    async def request_start(config, name, request, progress):
        await asyncio.Event().wait()

    async def drive() -> None:
        with (
            mock.patch("labnotes.tui.run_app.ensure_daemon", new=mock.AsyncMock()),
            mock.patch.object(app, "attach_daemon"),
            mock.patch("labnotes.tui.run_app.request_start", new=request_start),
            mock.patch.object(app, "set_interval", wraps=app.set_interval) as interval,
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert mock.call(0.1, app.spin_startup) in interval.call_args_list
                app.startup_timer.stop()

    asyncio.run(drive())


@mock.patch("labnotes.tui.run_app.SPINNER", "|/-\\")
def test_startup_spinner_steps_one_frame_per_tick_and_wraps(tmp_path: Path) -> None:
    app = starting_app(tmp_path)
    app.steps = ["Starting daemon"]
    startup = mock.Mock()
    with mock.patch.object(app, "query_one", return_value=startup):
        app.spin_startup()
        app.spin_startup()
        assert [call.args[0].plain for call in startup.update.call_args_list] == [
            "/ Starting daemon\n",
            "- Starting daemon\n",
        ]
        app.startup_frame = 3
        app.spin_startup()
    assert app.startup_frame == 0


def test_following_the_daemon_starts_stream_worker(tmp_path: Path) -> None:
    app = starting_app(tmp_path)
    app.daemon_journal = mock.Mock(path=tmp_path / "j.jsonl")
    with (
        mock.patch.object(app, "attach_daemon") as attach,
        mock.patch.object(app, "listen") as listen,
        mock.patch.object(app, "set_interval") as interval,
        mock.patch.object(app, "read_stream", new=mock.Mock()) as stream,
        mock.patch.object(app, "run_worker") as worker,
    ):
        app.follow_daemon()
        interval.assert_not_called()
        worker.assert_called_once_with(stream.return_value)
    attach.assert_called_once_with()
    listen.assert_called_once()


@pytest.mark.parametrize(
    ("hooks", "names"),
    [
        ((), ["runs"]),
        (("teardown",), ["runs", "teardown"]),
        (("teardown", "setup"), ["setup", "runs", "teardown"]),
    ],
)
def test_stages_run_in_order_whatever_order_hooks_arrive(
    hooks: tuple[str, ...], names: list[str]
) -> None:
    view = RunLiveView()
    view.hooks = hooks
    assert view.stage_names() == names


def test_a_later_single_run_plan_keeps_the_runs_table() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(planned("r1", "r2"))
        report(planned("r3"))
        await pilot.pause()
        assert app.body.viewing is None
        assert [row[0] for row in rows(app)] == ["r1", "r2", "r3"]

    drive_hooks(steps)


def test_a_first_single_run_plan_opens_its_output() -> None:
    async def steps(app: RunApp, pilot: Any, report: Report) -> None:
        report(planned("r1"))
        await pilot.pause()
        assert app.body.viewing == "r1"

    drive_hooks(steps)


def feed(path: Path, *batches: list[dict[str, object]]) -> mock.Mock:
    pending = list(batches)
    return mock.Mock(path=path, read=lambda: pending.pop(0) if pending else [])


def test_a_restart_plan_shows_as_a_retry_of_its_known_run(tmp_path: Path) -> None:
    restart: dict[str, object] = {
        "event": "planned",
        "title": "exp",
        "runs": [{"run": "r2", "params": {"m": "a"}}],
        "restart": "r1",
    }
    app = RunApp(
        None,
        "exp",
        COLUMNS,
        daemon_journal=feed(tmp_path / "j", [restart, {**restart, "restart": "r9"}]),
    )
    app.body.cells["r1"] = {"run": "r1"}
    with mock.patch.object(app.body, "show_event") as show:
        app.forward("j", restart)
        app.forward(str(tmp_path / "j"), {**restart, "restart": "r9"})
    assert show.call_args_list == [
        mock.call(
            {"event": "retried", "run": "r1", "retry": "r2", "params": {"m": "a"}}
        ),
        mock.call({**restart, "restart": "r9"}),
    ]


def test_idle_shows_only_once_every_streamed_batch_is_idle() -> None:
    app = RunApp(None, "exp", COLUMNS)
    with mock.patch.object(app.body, "show_event") as show:
        app.forward("one", {"event": "started"})
        app.forward("two", {"event": "started"})
        app.forward("one", {"event": "idle"})
        assert show.call_args_list == [
            mock.call({"event": "started"}),
            mock.call({"event": "started"}),
        ]
        app.forward("two", {"event": "idle"})
        assert show.call_args_list[2:] == [mock.call({"event": "idle"})]
    assert app.busy_journals == set()


def test_attached_app_follows_every_journal_and_controls_them_all(
    tmp_path: Path,
) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(None, "exp", COLUMNS, config, attach=True)
    paths = [str(tmp_path / "one.jsonl"), str(tmp_path / "two.jsonl")]

    async def drive() -> None:
        with (
            mock.patch.object(app, "attach_daemon", return_value=paths),
            mock.patch.object(app, "queue_command") as queue,
            mock.patch.object(app, "read_stream", new=mock.AsyncMock()) as stream,
        ):
            async with app.run_test() as pilot:
                await pilot.pause(1.2)
                stream.assert_awaited_once()
                assert app.daemon_journal is not None
                assert str(app.daemon_journal.path) == paths[0]
                app.controls.set_concurrency(3)
                queue.assert_called_once_with(
                    {"command": "set_concurrency", "count": 3, "journal": None}
                )
                app.exit()

    asyncio.run(drive())


def test_attached_app_with_nothing_running_says_so_and_exits(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    app = RunApp(None, "exp", COLUMNS, config, attach=True)

    async def drive() -> None:
        with (
            mock.patch.object(app, "attach_daemon", return_value=[]),
            mock.patch.object(app, "listen") as listen,
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert not app.is_running
        listen.assert_not_called()

    asyncio.run(drive())
    assert app.farewell == "Nothing is running for exp."
    assert app.daemon_journal is None


def test_detached_app_does_not_poll_for_journals(tmp_path: Path) -> None:
    config = mock.Mock(root=tmp_path, experiments="{experiment}", defaults={})
    journal = mock.Mock(path=tmp_path / "one.jsonl")
    journal.read.return_value = []
    app = RunApp(None, "exp", COLUMNS, config, daemon_journal=journal)

    async def drive() -> None:
        with (
            mock.patch.object(app, "attach_daemon", return_value=["/other"]),
            mock.patch.object(app, "read_stream", new=mock.AsyncMock()) as stream,
        ):
            async with app.run_test() as pilot:
                await pilot.pause(1.2)
                stream.assert_awaited_once()
                journal.read.assert_not_called()
                app.exit()

    asyncio.run(drive())


@pytest.mark.parametrize("body_ready", [True, False])
@pytest.mark.parametrize("ending", [b"", b"broken json\n", OSError("lost")])
def test_stream_delivers_envelopes_and_keeps_state_on_disconnect(
    body_ready: bool, ending: bytes | Exception
) -> None:
    app = RunApp(None, "exp", COLUMNS)
    app.attached = mock.Mock()
    app.body_ready = body_ready
    app.body.concurrency = 3
    reader, writer, label = mock.Mock(), mock.Mock(), mock.Mock()
    event = {"event": "idle", "at": 123}
    reader.readline = mock.AsyncMock(
        side_effect=[
            json.dumps({"journal": "batch", "event": event}).encode() + b"\n",
            ending,
        ]
    )
    with (
        mock.patch(
            "labnotes.tui.run_app.asyncio.open_connection",
            new=mock.AsyncMock(return_value=(reader, writer)),
        ),
        mock.patch.object(app, "query_one", return_value=label),
        mock.patch.object(app, "forward") as forward,
    ):
        asyncio.run(app.read_stream())
    assert app.disconnected
    writer.close.assert_called_once_with()
    label.update.assert_called_once_with("3 at a time · disconnected")
    if body_ready:
        forward.assert_called_once_with("batch", event)
    else:
        forward.assert_not_called()


def test_stream_reads_lines_up_to_sixteen_mebibytes() -> None:
    app = RunApp(None, "exp", COLUMNS)
    app.attached = mock.Mock()
    reader, writer = mock.Mock(), mock.Mock()
    reader.readline = mock.AsyncMock(return_value=b"")
    with (
        mock.patch(
            "labnotes.tui.run_app.asyncio.open_connection",
            new=mock.AsyncMock(return_value=(reader, writer)),
        ) as connect,
        mock.patch.object(app, "query_one"),
    ):
        asyncio.run(app.read_stream())
    connect.assert_awaited_once_with(sock=app.attached, limit=16 * 1024 * 1024)


def test_stream_ending_after_the_screen_is_gone_does_not_crash() -> None:
    app = RunApp(None, "exp", COLUMNS)
    app.attached = mock.Mock()
    with (
        mock.patch(
            "labnotes.tui.run_app.asyncio.open_connection",
            new=mock.AsyncMock(side_effect=OSError("closed")),
        ),
        mock.patch.object(app, "query_one", side_effect=NoMatches("gone")),
    ):
        asyncio.run(app.read_stream())
    assert app.disconnected


def test_stream_connection_error_is_shown_without_crashing() -> None:
    app = RunApp(None, "exp", COLUMNS)
    app.attached = mock.Mock()
    label = mock.Mock()
    with (
        mock.patch(
            "labnotes.tui.run_app.asyncio.open_connection",
            new=mock.AsyncMock(side_effect=OSError("gone")),
        ),
        mock.patch.object(app, "query_one", return_value=label),
    ):
        asyncio.run(app.read_stream())
    assert app.disconnected
    label.update.assert_called_once_with("1 at a time · disconnected")


def test_disconnected_controls_do_not_send_or_start_a_daemon(tmp_path: Path) -> None:
    app = starting_app(tmp_path)
    app.disconnected = True
    with (
        mock.patch("labnotes.tui.run_app.daemon_command") as command,
        mock.patch("labnotes.tui.run_app.request_start") as start,
        mock.patch.object(app.body, "show") as show,
    ):
        asyncio.run(app.send_command({"command": "set_concurrency", "count": 2}))
        asyncio.run(app.restart_daemon_run("r1"))
    command.assert_not_called()
    start.assert_not_called()
    assert show.call_args_list == [mock.call("disconnected"), mock.call("disconnected")]


def test_start_attaches_before_requesting_a_fast_batch(tmp_path: Path) -> None:
    app = starting_app(tmp_path)
    order: list[str] = []

    async def ensure(*args):
        assert app.steps == ["Starting daemon"]
        order.append("ensure")

    def attach():
        order.append("attach")
        return []

    async def start(*args):
        order.append("start")
        return {"journal": "fast-batch"}

    app.startup_timer = mock.Mock()
    with (
        mock.patch("labnotes.tui.run_app.ensure_daemon", new=ensure),
        mock.patch.object(app, "attach_daemon", new=attach),
        mock.patch("labnotes.tui.run_app.request_start", new=start),
        mock.patch.object(
            app, "follow_daemon", side_effect=lambda: order.append("follow")
        ),
        mock.patch.object(app, "query_one"),
        mock.patch.object(app, "call_after_refresh"),
    ):
        asyncio.run(app.start_daemon_run())
    assert order == ["ensure", "attach", "start", "follow"]
    assert app.daemon_journal is not None
    assert str(app.daemon_journal.path) == "fast-batch"


@pytest.mark.parametrize("attach", [False, True])
def test_run_stream_filters_other_batches_but_follows_its_restarts(
    tmp_path: Path, attach: bool
) -> None:
    app = RunApp(
        None, "exp", COLUMNS, daemon_journal=mock.Mock(path=Path("own")), attach=attach
    )
    app.body.cells["r1"] = {"run": "r1"}
    old: dict[str, object] = {
        "event": "planned",
        "runs": [{"run": "old", "params": {}}],
    }
    own = {"event": "concurrency", "concurrency": 2}
    restart: dict[str, object] = {
        "event": "planned",
        "restart": "r1",
        "runs": [{"run": "r2", "params": {}}],
    }
    ended: dict[str, object] = {"event": "ended", "run": "r2"}
    with mock.patch.object(app.body, "show_event") as show:
        app.forward("previous", old)
        app.forward("unrelated", {**restart, "restart": "other"})
        app.forward("own", own)
        app.forward("restart", restart)
        app.forward("restart", ended)
    expected = [
        own,
        {"event": "retried", "run": "r1", "retry": "r2", "params": {}},
        ended,
    ]
    if attach:
        expected = [old, {**restart, "restart": "other"}, *expected]
    assert show.call_args_list == [mock.call(event) for event in expected]
