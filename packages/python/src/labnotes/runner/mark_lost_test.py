import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.mark_lost import mark_lost

GOING: dict[str, object] = {"params": {"n": 1}, "ended": None, "exit_code": None}
LOST = {"ended": "1970-01-01T00:01:40Z", "ended_by": "lost"}


@pytest.fixture
def write() -> Iterator[mock.MagicMock]:
    with (
        mock.patch("labnotes.runner.mark_lost.write_run_json") as write,
        mock.patch("labnotes.runner.mark_lost.time") as time,
    ):
        time.time.return_value = 100
        yield write


def put(folder: Path, content: object) -> None:
    text = content if isinstance(content, str) else json.dumps(content)
    (folder / "run.json").write_text(text, encoding="utf-8")


def test_marks_an_unfinished_run_lost_from_its_record_on_disk(
    write: mock.MagicMock, tmp_path: Path
) -> None:
    put(tmp_path, {**GOING, "note": "kept"})

    mark_lost(tmp_path)

    write.assert_called_once_with(tmp_path, {**GOING, "note": "kept", **LOST})


def test_marks_only_the_last_invocation_lost(
    write: mock.MagicMock, tmp_path: Path
) -> None:
    run = {
        **GOING,
        "invocations": [{"exit_code": 1}, {"exit_code": 2}, {"started": "s"}],
    }
    put(tmp_path, run)

    mark_lost(tmp_path)

    write.assert_called_once_with(
        tmp_path,
        {
            **run,
            **LOST,
            "invocations": [
                {"exit_code": 1},
                {"exit_code": 2},
                {"started": "s", **LOST},
            ],
        },
    )


@pytest.mark.parametrize(
    "disk",
    [
        {**GOING, "ended": "2026-01-01T00:00:00Z", "exit_code": 0},
        {**GOING, "ended": "2026-01-01T00:00:00Z"},
        {**GOING, "exit_code": 1},
        "{not json",
        "[]",
    ],
)
def test_leaves_a_finished_or_unreadable_run(
    write: mock.MagicMock, tmp_path: Path, disk: object
) -> None:
    put(tmp_path, disk)

    mark_lost(tmp_path)

    write.assert_not_called()


def test_leaves_a_run_whose_run_json_is_missing(
    write: mock.MagicMock, tmp_path: Path
) -> None:
    mark_lost(tmp_path)

    write.assert_not_called()
