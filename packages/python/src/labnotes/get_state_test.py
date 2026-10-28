from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.get_state import get_state


@pytest.fixture(autouse=True)
def path(tmp_path: Path) -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.get_state.state_path", return_value=tmp_path / "state.json"
    ) as mocked:
        yield mocked


def test_raises_outside_an_invocation(path: mock.MagicMock) -> None:
    path.side_effect = RuntimeError("no invocation")
    with pytest.raises(RuntimeError, match="no invocation"):
        get_state()


def test_returns_empty_state_before_setup_writes() -> None:
    assert get_state() == {}


@pytest.mark.parametrize("content", ["not JSON", "[]"])
def test_reports_invalid_state(tmp_path: Path, content: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        get_state()


def test_reads_saved_state(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text('{"resource": "one"}')
    assert get_state() == {"resource": "one"}
