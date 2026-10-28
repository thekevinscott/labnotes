from pathlib import Path

import pytest

from labnotes.state_path import state_path


def test_reads_the_current_hook_path(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("/outer/state.json", "/inner/state.json"):
        monkeypatch.setenv("LABNOTES_STATE", value)
        assert state_path() == Path(value)
