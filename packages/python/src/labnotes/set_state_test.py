import json
from pathlib import Path

import pytest

from labnotes.set_state import set_state


def test_raises_outside_a_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LABNOTES_STATE", raising=False)
    with pytest.raises(RuntimeError, match="setup and teardown hooks"):
        set_state({})


def test_merges_keys_and_replaces_values_without_deep_merging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state.json"
    monkeypatch.setenv("LABNOTES_STATE", str(path))

    set_state({"container": "one", "options": {"old": True}})
    set_state({"port": 8000, "options": {"new": [None, "ü"]}})
    set_state({})

    assert json.loads(path.read_text()) == {
        "container": "one",
        "port": 8000,
        "options": {"new": [None, "ü"]},
    }


def test_invalid_values_leave_saved_state_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state.json"
    monkeypatch.setenv("LABNOTES_STATE", str(path))
    set_state({"container": "one"})
    with pytest.raises(TypeError):
        set_state({"invalid": object()})
    assert json.loads(path.read_text()) == {"container": "one"}
