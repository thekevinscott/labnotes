import json
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.run_status import run_status


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.run_status.load_config") as load_config,
        mock.patch(
            "labnotes.run_status.watch_status", new=mock.AsyncMock()
        ) as watch_status,
    ):
        yield {"load_config": load_config, "watch_status": watch_status}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        run_status.main(argv, prog_name="status")
    return exit_info.value.code


EVENTS: list[dict[str, object]] = [
    {"event": "queued", "experiment": "exp", "run": "r2"},
    {"event": "done", "experiment": "exp", "error": None, "at": Path("/x")},
]


def report(_: object, __: bool, emit: Callable[[dict[str, object]], None]) -> None:
    for event in EVENTS:
        emit(event)


@pytest.mark.parametrize(
    ("argv", "follow"),
    [([], False), (["--follow"], True), (["-f"], True)],
)
def test_shows_status(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    argv: list[str],
    follow: bool,
) -> None:
    collaborators["watch_status"].side_effect = report

    assert run(argv) == 0

    root = collaborators["load_config"].return_value.root
    collaborators["watch_status"].assert_awaited_once_with(root, follow, mock.ANY)
    assert capsys.readouterr().out == "exp: r2 runs next.\nexp: Done.\n"


def test_shows_status_as_json_lines(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["watch_status"].side_effect = report

    assert run(["--json"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert [json.loads(line) for line in lines] == [
        EVENTS[0],
        {**EVENTS[1], "at": "/x"},
    ]


def test_status_ends_quietly_on_ctrl_c(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["watch_status"].side_effect = KeyboardInterrupt

    assert run(["-f"]) == 0

    assert capsys.readouterr().out == ""


def test_status_needs_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run([]) == 1

    assert "No .labnotes.toml here" in capsys.readouterr().err
    collaborators["watch_status"].assert_not_awaited()
