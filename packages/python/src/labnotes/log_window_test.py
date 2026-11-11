from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from labnotes.log_window import log_window


@pytest.fixture
def index() -> Iterator[mock.Mock]:
    with mock.patch("labnotes.log_window.LineIndex") as made:
        made.return_value.read.return_value = [b"caf\xc3\xa9", b"\xff"]
        made.return_value.scanned = 0
        yield made


def test_indexes_a_log_once_and_decodes_the_window(
    tmp_path: Path, index: mock.Mock
) -> None:
    path = tmp_path / "stdout.log"
    path.write_text("ab\n")
    indexes: dict[Path, Any] = {}
    assert log_window(indexes, path, 2, 5) == ["café", "�"]
    assert log_window(indexes, path, 0, 1) == ["café", "�"]
    index.assert_called_once_with(path)
    assert indexes == {path: index.return_value}
    assert index.return_value.extend.call_count == 2
    assert index.return_value.read.call_args_list == [mock.call(2, 5), mock.call(0, 1)]


@pytest.mark.parametrize(("scanned", "fresh"), [(3, False), (4, True)])
def test_starts_over_when_the_log_shrank(
    tmp_path: Path, index: mock.Mock, scanned: int, fresh: bool
) -> None:
    path = tmp_path / "stdout.log"
    path.write_text("ab\n")
    old = mock.Mock(scanned=scanned, **{"read.return_value": []})
    indexes = {path: old}
    log_window(indexes, path, 0, 1)  # type: ignore[arg-type]
    assert (indexes[path] is index.return_value) is fresh
    assert (old.extend.called) is not fresh
