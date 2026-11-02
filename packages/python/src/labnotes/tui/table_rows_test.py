from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.table_rows import table_rows

COLUMNS = [{"key": "id", "label": "Run"}]


@pytest.fixture(autouse=True)
def run_cells() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.tui.table_rows.run_cells",
        side_effect=lambda row, columns: ["cells", row, columns],
    ) as found:
        yield found


def test_lists_each_run_in_order_keyed_by_its_folder() -> None:
    runs = [{"folder": "alpha/runs/b"}, {"folder": "alpha/runs/a/1"}]
    rows = {"alpha/runs/a/1": {"id": "a/1"}, "alpha/runs/b": {"id": "b"}}

    assert table_rows(runs, COLUMNS, rows) == [
        ("alpha/runs/b", ["cells", {"id": "b"}, COLUMNS]),
        ("alpha/runs/a/1", ["cells", {"id": "a/1"}, COLUMNS]),
    ]
