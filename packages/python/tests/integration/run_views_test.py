import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import psutil
import pytest
from textual.widgets import Static

from labnotes.models import LabnotesConfig
from labnotes.tui.run_app import RunApp


@pytest.fixture
def runtime() -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": folder}):
            yield Path(folder)


def stop_daemons(root: Path) -> None:
    config = str(root / ".labnotes.toml")
    owners = [
        process
        for process in psutil.process_iter(["cmdline"])
        if config in (process.info["cmdline"] or [])
    ]
    for process in owners:
        process.terminate()
    psutil.wait_procs(owners, timeout=15)


def test_run_app_mounts_configured_view_and_digits_switch(
    tmp_path: Path, runtime: Path
) -> None:
    async def drive() -> None:
        (tmp_path / ".labnotes.toml").write_text("")
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
            for _ in range(300):
                await pilot.pause(0.05)
                if app.query("#view-2"):
                    break
            await pilot.pause(0.2)
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

    try:
        asyncio.run(drive())
    finally:
        stop_daemons(tmp_path)


def test_views_share_the_selected_run_and_stop_runs(
    tmp_path: Path, runtime: Path
) -> None:
    async def drive() -> None:
        (tmp_path / ".labnotes.toml").write_text("")
        (tmp_path / "alpha").mkdir()
        (tmp_path / "alpha/experiment.toml").write_text(
            'command = "echo ok"\ncontinues = false\n[views]\n'
            'picker = "views.py:Picker"\nshown = "views.py:Shown"\n'
        )
        (tmp_path / "views.py").write_text(
            "from textual.widgets import Static\n"
            "from labnotes.view import Changed, Select, Selected, Stop\n"
            "class Picker(Static):\n"
            "    def on_labnotes_changed(self, message: Changed):\n"
            "        run = message.experiment.runs[0]['id']\n"
            "        self.post_message(Select(run))\n"
            "        self.post_message(Stop(run))\n"
            "class Shown(Static):\n"
            "    def on_labnotes_selected(self, message: Selected):\n"
            "        self.update(f'selected {message.run}')\n"
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
        controls = mock.Mock()

        async def start(report, listen):
            listen(controls)
            await waiting.wait()
            return []

        app = RunApp(start, "alpha", ("run", "status"), config=config)
        async with app.run_test() as pilot:
            for _ in range(300):
                await pilot.pause(0.05)
                if app.selected is not None:
                    break
            await pilot.pause(0.2)
            assert app.selected == "first"
            assert "selected first" in str(
                app.query_one("#view-3 Static", Static).content
            )
            controls.kill.assert_called_once_with("first")
            waiting.set()

    try:
        asyncio.run(drive())
    finally:
        stop_daemons(tmp_path)
