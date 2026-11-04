import hashlib
import json
import os
from pathlib import Path
from unittest import mock

import pytest

from labnotes.runner.run_state import RunState, journal_folder


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


def test_reader_waits_for_its_invocation_journal_to_appear(tmp_path: Path) -> None:
    reader = state(tmp_path)
    assert reader.read() == []
    reader.record({"event": "planned", "runs": []})
    assert [event["event"] for event in reader.read()] == ["planned"]


def test_journal_lives_in_state_home_not_runs_folder(tmp_path: Path) -> None:
    journal = state(tmp_path).path
    assert journal.is_relative_to(os.environ["XDG_STATE_HOME"])
    assert not journal.is_relative_to(tmp_path)


def test_journal_folder_is_stable_per_runs_folder(tmp_path: Path) -> None:
    runs = tmp_path / "experiments/exp/runs"
    assert journal_folder(runs) == journal_folder(
        tmp_path / "experiments/exp/../exp/runs"
    )
    assert journal_folder(runs) != journal_folder(tmp_path / "other/runs")
    assert (
        journal_folder(runs).parent
        == Path(os.environ["XDG_STATE_HOME"]) / "labnotes/run-state"
    )


def test_journal_folder_defaults_to_local_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_STATE_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    folder = journal_folder(tmp_path / "runs")
    assert folder.parent == tmp_path / ".local/state/labnotes/run-state"


def test_empty_state_home_falls_back_to_local_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    folder = journal_folder(tmp_path / "runs")
    assert folder.parent == tmp_path / ".local/state/labnotes/run-state"


def test_journal_names_have_stable_folder_key_and_unique_eight_digit_nonce(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "experiments/exp/runs"
    folder = journal_folder(runs)
    expected = hashlib.sha256(str(runs.resolve()).encode()).hexdigest()[:16]
    assert folder.name == expected
    assert len(folder.name) == 16
    first, second = state(tmp_path), state(tmp_path)
    assert first.path.parent == folder
    assert first.path != second.path
    nonce = first.path.stem.rsplit("-", 1)[-1]
    assert len(nonce) == 8
    assert all(character in "0123456789abcdef" for character in nonce)


def test_record_appends_without_overwriting_and_keeps_private_mode(
    tmp_path: Path,
) -> None:
    writer = state(tmp_path)
    old_umask = os.umask(0)
    try:
        writer.record({"event": "planned", "runs": []})
    finally:
        os.umask(old_umask)
    assert writer.path.stat().st_mode & 0o777 == 0o600
    writer.record({"event": "idle"})
    assert [event["event"] for event in RunState(writer.path).read()] == [
        "planned",
        "idle",
    ]


def test_retry_event_uses_value_equality_for_a_distinct_string(tmp_path: Path) -> None:
    name = "".join(("retry", "ing"))
    writer = state(tmp_path)
    writer.record({"event": name, "seconds": 5})
    [event] = RunState(writer.path).read()
    assert isinstance(event["at"], float)
    assert isinstance(event["retry_at"], float)
    assert event["retry_at"] == event["at"] + 5


def test_read_cursor_stops_at_complete_lines_and_resumes_exactly(
    tmp_path: Path,
) -> None:
    writer = state(tmp_path)
    writer.path.parent.mkdir(parents=True)
    first = b'{"event":"planned"}\n'
    second = b'{"event":"idle"}\n'
    writer.path.write_bytes(first + second[:1])
    reader = RunState(writer.path)
    assert reader.read() == [{"event": "planned"}]
    assert reader.offset == len(first)
    with writer.path.open("ab") as file:
        file.write(second[1:])
    assert reader.read() == [{"event": "idle"}]
    assert reader.offset == len(first + second)
    assert reader.read() == []


def test_empty_line_is_invalid_journal_data(tmp_path: Path) -> None:
    reader = state(tmp_path)
    reader.path.parent.mkdir(parents=True)
    reader.path.write_bytes(b"\n")
    with pytest.raises(json.JSONDecodeError):
        reader.read()
