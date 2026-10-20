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
    ],
)
def test_names_the_experiment(event: dict[str, object], said: str) -> None:
    assert describe_status({**event, "experiment": "exp"}) == said
