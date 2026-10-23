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
        ({"event": "queued", "run": "r2"}, "exp: r2 runs next."),
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
