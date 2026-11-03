import asyncio
import json
from pathlib import Path
from unittest import mock

from textual.widgets import Static

from labnotes.models import LabnotesConfig
from labnotes.tui.run_app import RunApp, RunLiveView
from labnotes.view.experiment import Experiment


COLUMNS = ("run", "params", "status", "time", "memory", "size")


def test_run_app_mounts_configured_view_and_digits_switch(tmp_path: Path) -> None:
    async def drive() -> None:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "alpha/experiment.toml").write_text(
            'command = "echo ok"\ncontinues = false\n[views]\nprogress = "progress.py:Progress"\n'
        )
        (tmp_path / "progress.py").write_text(
            "from textual.widgets import Static\n"
            "from labnotes.view import Changed\n"
            "class Progress(Static):\n"
            "    def on_labnotes_changed(self, message: Changed):\n"
            "        row = message.experiment.runs[0]\n"
            '        self.update(f\'{message.experiment.name}: {row["folder"]} {row["status"]}\')\n'
        )
        run = tmp_path / "alpha/runs/first"
        run.mkdir(parents=True)
        (run / "run.json").write_text(
            json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0})
        )
        config = LabnotesConfig(
            tmp_path / ".labnotes.toml",
            tmp_path,
            "{experiment}",
            "{experiment}/files/",
            "{experiment}/runs/{run}",
        )
        waiting = asyncio.Event()

        async def start(report, listen):
            await waiting.wait()
            return []

        app = RunApp(start, "alpha", ("run", "status"), config=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#view-2")
            await pilot.press("2")
            assert app.query_one("#view-2").display
            assert "alpha: alpha/runs/first passed" in str(
                app.query_one("#view-2 Static", Static).content
            )
            await pilot.press("escape")
            await pilot.pause()
            assert app.query_one("#view-1").display
            await pilot.press("2")
            await pilot.press("1")
            await pilot.pause()
            assert app.query_one("#view-1").display
            waiting.set()

    asyncio.run(drive())


def test_no_custom_views_opens_no_tables(tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/experiment.toml").write_text(
        'command = "echo ok"\ncontinues = false\n[views]\nruns = "echo"\n'
    )
    config = LabnotesConfig(
        tmp_path / ".labnotes.toml", tmp_path, "{experiment}", "", ""
    )

    async def start(report, listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "alpha", COLUMNS, config)
        with mock.patch("labnotes.tui.run_app.open_tables") as open_tables:
            async with app.run_test() as pilot:
                await pilot.pause()
                assert app.query_one(RunLiveView)
                open_tables.assert_not_called()

    asyncio.run(drive())


def test_builtin_view_failure_stays_in_its_pane(tmp_path: Path) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/experiment.toml").write_text(
        'command = "echo ok"\ncontinues = false\n[views]\nprogress = "progress.py:Progress"\n'
    )
    config = LabnotesConfig(
        tmp_path / ".labnotes.toml", tmp_path, "{experiment}", "", ""
    )

    async def start(report, listen) -> list[dict[str, object]]:
        return await asyncio.get_running_loop().create_future()  # type: ignore[no-any-return]

    async def drive() -> None:
        app = RunApp(start, "alpha", COLUMNS, config)
        with mock.patch(
            "labnotes.tui.view_pane.load_view", side_effect=ImportError("broken")
        ):
            async with app.run_test() as pilot:
                await pilot.pause()
                assert not app.body_ready
                assert "broken" in str(app.query_one("#view-1 .failure").render())

    asyncio.run(drive())


def test_missing_or_invalid_config_uses_default_views(tmp_path: Path) -> None:
    config = LabnotesConfig(
        tmp_path / ".labnotes.toml",
        tmp_path,
        "{experiment}",
        "",
        "",
        defaults={"views": {"progress": "progress.py:Progress"}},
    )

    async def start(report, listen) -> list[dict[str, object]]:
        return []

    app = RunApp(start, "alpha", COLUMNS, config)
    assert app.view_specs == {"progress": "progress.py:Progress"}
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/experiment.toml").write_text("[bad")
    app = RunApp(start, "alpha", COLUMNS, config)
    assert app.view_specs == {"progress": "progress.py:Progress"}


def test_missing_loaded_experiment_keeps_views_empty(tmp_path: Path) -> None:
    config = LabnotesConfig(
        tmp_path / ".labnotes.toml", tmp_path, "{experiment}", "", ""
    )

    async def start(report, listen) -> list[dict[str, object]]:
        return []

    app = RunApp(start, "alpha", COLUMNS, config)
    with mock.patch(
        "labnotes.tui.run_app.load_experiment", new=mock.AsyncMock(return_value=None)
    ):
        asyncio.run(app.load_data(mock.Mock()))
    assert app.shown is None
    assert not app.loaded_views


def test_run_file_change_delivers_relative_path_to_views(tmp_path: Path) -> None:
    config = LabnotesConfig(
        tmp_path / ".labnotes.toml", tmp_path, "{experiment}", "", ""
    )

    async def start(report, listen) -> list[dict[str, object]]:
        return []

    app = RunApp(start, "alpha", COLUMNS, config)
    app.shown = Experiment(tmp_path, "alpha", ())

    async def changes():
        yield {"path": "alpha/runs/first/stdout.log"}

    with (
        mock.patch("labnotes.tui.run_app.watch_rows", return_value=changes()),
        mock.patch.object(app, "deliver") as deliver,
    ):
        asyncio.run(app.watch_files(mock.Mock()))
    deliver.assert_called_once_with(
        app.shown, frozenset({"alpha/runs/first/stdout.log"})
    )
