import json
from pathlib import Path
from unittest import mock

from labnotes.runner.run_state import RunState


def state(tmp_path: Path) -> RunState:
    config = mock.Mock(root=tmp_path, runs="experiments/{experiment}/runs/{run}")
    return RunState.create(config, "exp")


def test_replays_complete_events_once_and_waits_for_partial_lines(
    tmp_path: Path,
) -> None:
    writer = state(tmp_path)
    writer.record({"event": "planned", "runs": [{"run": "one", "params": {}}]})
    reader = RunState(writer.path)
    first = reader.read()
    assert first[0]["event"] == "planned"
    assert isinstance(first[0]["at"], float)
    assert first[0]["at"] > 0
    assert reader.read() == []
    with writer.path.open("ab") as file:
        file.write(b'{"event": "setting up"')
    assert reader.read() == []
    with writer.path.open("ab") as file:
        file.write(b"}\n")
    assert reader.read() == [{"event": "setting up"}]


def test_retry_deadline_and_new_invocation_are_replayable(tmp_path: Path) -> None:
    writer = state(tmp_path)
    writer.record({"event": "retrying", "run": "one", "seconds": 30})
    reader = RunState(writer.path)
    [retry] = reader.read()
    assert isinstance(retry["at"], float)
    assert isinstance(retry["retry_at"], float)
    assert retry["retry_at"] == retry["at"] + 30
    second = state(tmp_path)
    second.record({"event": "idle"})
    assert second.path != writer.path
    assert reader.read() == []
    assert [event["event"] for event in RunState(second.path).read()] == ["idle"]
    assert json.loads(writer.path.read_text().splitlines()[0])["event"] == "retrying"
