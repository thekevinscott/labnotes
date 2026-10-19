from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.runner.describe_event import describe_event


@pytest.fixture(autouse=True)
def param_args() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.runner.describe_event.param_args", return_value=["--m", "a"]
    ) as param_args:
        yield param_args


@pytest.mark.parametrize(
    ("event", "line"),
    [
        (
            {"event": "planned", "runs": [{}] * 4, "concurrency": 2},
            "4 runs to go, 2 at a time.",
        ),
        ({"event": "queued", "run": "r1"}, "r1 runs next."),
        ({"event": "deselected", "run": "r1"}, "r1 deselected."),
        ({"event": "stopping run", "run": "r1"}, "Stopping r1."),
        ({"event": "killing run", "run": "r1"}, "Killing r1."),
        ({"event": "reselected", "run": "r1"}, "r1 back in the queue."),
        ({"event": "concurrency", "concurrency": 3}, "3 at a time."),
        (
            {"event": "ended", "run": "r1", "exit_code": 3, "error": None},
            "r1 exited 3",
        ),
        (
            {"event": "ended", "run": "r1", "exit_code": None, "error": "boom"},
            "r1 boom",
        ),
        ({"event": "stopping"}, "Stopping runs. Ctrl-C again to kill them."),
        ({"event": "killing"}, "Killing runs."),
    ],
)
def test_describes_an_event(event: dict[str, object], line: str) -> None:
    assert describe_event(event) == line


def test_describes_a_started_run_with_its_args(param_args: mock.MagicMock) -> None:
    event: dict[str, object] = {"event": "started", "run": "r1", "params": {"m": "a"}}

    assert describe_event(event) == "r1 started --m a"
    param_args.assert_called_once_with({"m": "a"})


def test_describes_a_started_run_without_params(param_args: mock.MagicMock) -> None:
    param_args.return_value = []

    assert describe_event({"event": "started", "run": "r1", "params": {}}) == (
        "r1 started"
    )
