from pathlib import Path

import pytest

from labnotes.get_state import get_state


@pytest.mark.parametrize("value", [None, ""])
def test_raises_outside_a_hook(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    monkeypatch.delenv("LABNOTES_STATE", raising=False)
    if value is not None:
        monkeypatch.setenv("LABNOTES_STATE", value)
    with pytest.raises(RuntimeError, match="setup and teardown hooks"):
        get_state()


def test_returns_empty_state_before_setup_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LABNOTES_STATE", str(tmp_path / "state.json"))
    assert get_state() == {}


@pytest.mark.parametrize("content", ["not JSON", "[]"])
def test_reports_invalid_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    path = tmp_path / "state.json"
    path.write_text(content)
    monkeypatch.setenv("LABNOTES_STATE", str(path))
    with pytest.raises(ValueError):
        get_state()
