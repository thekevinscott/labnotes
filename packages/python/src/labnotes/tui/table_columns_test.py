from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.table_columns import table_columns

CONFIG = {"params": {"m": [1, 2]}}


@pytest.fixture(autouse=True)
def run_columns() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.tui.table_columns.run_columns",
        side_effect=lambda config: ["id", "m", "started"],
    ) as found:
        yield found


def test_lists_a_status_column_then_the_run_columns(
    run_columns: mock.MagicMock,
) -> None:
    assert table_columns(CONFIG) == [
        {"key": "status", "label": ""},
        {"key": "id", "label": "id"},
        {"key": "m", "label": "m"},
        {"key": "started", "label": "started"},
    ]
    run_columns.assert_called_once_with(CONFIG)
