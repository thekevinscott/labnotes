import asyncio
import json
from pathlib import Path

from conftest import write
from starlette.testclient import TestClient
from textual.app import App, ComposeResult

from labnotes.create_app import create_app
from labnotes.read_config import read_config
from labnotes.tui.stream_log import StreamLog

OUTPUT = (
    "crlf first\r\n"
    "crlf second\r\n"
    "step 0\rstep 1\rstep 2\r\n"
    "\x1b[31mred\x1b[0m\r\n"
    "loading 0\rloading 1\r"
)
SHOWN = ["crlf first", "crlf second", "step 2", "red", "loading 1"]


class Host(App[None]):
    def compose(self) -> ComposeResult:
        yield StreamLog("stdout", id="log")


def test_tui_shows_the_last_overwrite_of_each_line(tmp_path: Path) -> None:
    (tmp_path / "stdout.log").write_bytes(OUTPUT.encode())

    async def drive() -> list[str]:
        app = Host()
        async with app.run_test(size=(40, 10)) as pilot:
            log = app.query_one(StreamLog)
            log.follow(tmp_path)
            await pilot.pause()
            return [log.render_line(y).text.rstrip() for y in range(log.rows)]

    assert asyncio.run(drive()) == SHOWN


def test_web_lines_show_the_last_overwrite_of_each_line(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    write(
        tmp_path / "alpha/runs/run1/run.json",
        json.dumps({"params": {}, "created": "2026-11-10T00:00:00Z"}),
    )
    (tmp_path / "alpha/runs/run1/stdout.log").write_bytes(OUTPUT.encode())
    app = create_app(read_config(tmp_path / ".labnotes.toml"))
    with TestClient(app) as client:
        response = client.get(
            "/experiments/alpha/lines/run1",
            params={"file": "stdout.log", "first": 0, "count": 10},
        )
    assert response.status_code == 200
    assert response.json()["lines"] == [
        "crlf first",
        "crlf second",
        "step 2",
        "\x1b[31mred\x1b[0m",
        "loading 1",
    ]
