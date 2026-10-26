import pytest

from labnotes.daemon.describe_status import describe_status


@pytest.mark.parametrize(
    ("event", "said"),
    [
        (
            {"event": "output", "run": "r1", "stream": "stdout", "line": "hi"},
            "exp: r1: hi",
        ),
        ({"event": "done", "error": None}, "exp: Done."),
        ({"event": "done", "error": "boom"}, "exp: Stopped: boom"),
        ({"event": "stopping run", "run": "r2"}, "exp: Stopping r2."),
        (
            {"event": "usage", "run": "r1", "memory": 3_200_000_000, "size": 5000},
            "exp: r1 uses 3.2 GB of memory, 5.0 kB on disk.",
        ),
        (
            {"event": "usage", "run": "r1", "memory": None, "size": None},
            "exp: r1 uses ? of memory, ? on disk.",
        ),
    ],
)
def test_names_the_experiment(event: dict[str, object], said: str) -> None:
    assert describe_status({**event, "experiment": "exp"}) == said


def test_adds_a_failed_runs_last_stderr_line() -> None:
    event = {
        "event": "ended",
        "experiment": "exp",
        "run": "r1",
        "exit_code": 1,
        "error": None,
        "last_stderr": "ValueError: boom",
    }

    assert describe_status(event) == "exp: r1 exited 1: ValueError: boom"


def test_describes_an_ended_run_without_stderr_as_before() -> None:
    event = {"event": "ended", "experiment": "exp", "run": "r1", "exit_code": 1}

    assert describe_status({**event, "error": None}) == "exp: r1 exited 1"
