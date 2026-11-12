from pathlib import Path
from unittest import mock

from labnotes.runner.stamp_event import stamp_event


def test_stamps_the_time_and_returns_json_safe_values(tmp_path: Path) -> None:
    source = {"event": "started", "run": "r1", "folder": tmp_path}
    with mock.patch("labnotes.runner.stamp_event.time.time", return_value=100.0):
        stamped = stamp_event(source)
    assert stamped == {
        "event": "started",
        "run": "r1",
        "folder": str(tmp_path),
        "at": 100.0,
    }
    assert "at" not in source


def test_a_retry_carries_its_deadline() -> None:
    name = "".join(("retry", "ing"))
    with mock.patch("labnotes.runner.stamp_event.time.time", return_value=100.0):
        stamped = stamp_event({"event": name, "run": "r1", "seconds": 5})
    assert stamped["retry_at"] == 105.0


def test_other_events_have_no_deadline() -> None:
    assert "retry_at" not in stamp_event({"event": "idle", "seconds": 5})
