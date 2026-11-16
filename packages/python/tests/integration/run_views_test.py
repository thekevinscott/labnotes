import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil
import pytest
from textual.widgets import Static

from labnotes.models import LabnotesConfig
from labnotes.tui.run_app import RunApp


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    with TemporaryDirectory(prefix="ln-runtime-") as folder:
        monkeypatch.setenv("XDG_RUNTIME_DIR", folder)
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
