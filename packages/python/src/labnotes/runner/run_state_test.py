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
