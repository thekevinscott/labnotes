import json
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.set_state import set_state


@pytest.fixture(autouse=True)
def path(tmp_path: Path) -> Iterator[mock.MagicMock]:
    with (
        mock.patch(
            "labnotes.set_state.state_path", return_value=tmp_path / "state.json"
        ) as mocked,
        mock.patch(
            "labnotes.set_state.get_state",
            return_value={"container": "one", "options": {"old": True}},
        ),
    ):
        yield mocked


def test_requires_writable_hook_state(path: mock.MagicMock) -> None:
    path.side_effect = RuntimeError("not writable")
    with pytest.raises(RuntimeError, match="not writable"):
        set_state({})
    path.assert_called_once_with(writable=True)


def test_merges_keys_and_replaces_values_without_deep_merging(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    set_state({"port": 8000, "options": {"new": [None, "ü"]}})

    assert json.loads(path.read_text()) == {
        "container": "one",
        "port": 8000,
        "options": {"new": [None, "ü"]},
    }


def test_invalid_values_leave_saved_state_intact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"container": "one"}')
    with pytest.raises(TypeError):
        set_state({"invalid": object()})
    assert json.loads(path.read_text()) == {"container": "one"}
