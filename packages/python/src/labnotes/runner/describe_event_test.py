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
        (
            {"event": "planned", "runs": [], "concurrency": 2},
            "Nothing to run: every combination has its repeats.",
        ),
        ({"event": "retried", "run": "r1", "retry": "r2"}, "r1 retried as r2."),
        ({"event": "retried", "run": "r1", "retry": "r1"}, "r1 retried in its folder."),
        (
            {
                "event": "retrying",
                "run": "r1",
                "attempt": 2,
                "retries": 3,
                "seconds": 60.0,
            },
            "r1 retries in 1m 00s (retry 2 of 3).",
        ),
        (
            {"event": "gave up", "run": "r1", "retries": 2},
            "r1 gave up (exit 75) after 2 retries.",
        ),
        (
            {"event": "gave up", "run": "r1", "retries": 1, "exit_code": 1},
            "r1 gave up (exit 1) after 1 retries.",
        ),
        (
            {"event": "capped", "runs": ["r1"], "retries": 3},
            "1 cell gave up after 3 retries.",
        ),
        (
            {"event": "capped", "runs": ["r1", "r2"], "retries": 0},
            "2 cells gave up after 0 retries.",
        ),
        ({"event": "retry cancelled", "run": "r1"}, "r1 won't retry."),
        ({"event": "idle"}, "No runs left."),
        ({"event": "stopping run", "run": "r1"}, "Stopping r1."),
        ({"event": "killing run", "run": "r1"}, "Killing r1."),
        ({"event": "held", "run": "r1"}, "r1 held by another run."),
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
        (
            {"event": "finishing up"},
            "Finishing up. Queued runs won't start; running cells will finish.",
        ),
        ({"event": "setting up"}, "Setting up."),
        ({"event": "tearing down"}, "Tearing down."),
        ({"event": "teardown failed", "error": "down broke"}, "down broke"),
        ({"event": "hook ended", "hook": "setup", "error": None}, "Setup finished."),
        ({"event": "hook ended", "hook": "setup", "error": "up broke"}, "up broke"),
        ({"event": "daemon error", "error": "run broke"}, "run broke"),
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


def test_retried_uses_value_equality_for_ids() -> None:
    run = "".join(["run", "-1"])
    retry = "".join(["run-", "1"])
    assert run == retry and run is not retry
    assert describe_event({"event": "retried", "run": run, "retry": retry}) == (
        "run-1 retried in its folder."
    )


def test_retried_does_not_treat_a_smaller_id_as_the_same_run() -> None:
    assert describe_event({"event": "retried", "run": "r2", "retry": "r1"}) == (
        "r2 retried as r1."
    )
