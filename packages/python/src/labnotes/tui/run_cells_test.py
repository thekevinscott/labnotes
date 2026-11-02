from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.tui.run_cells import run_cells

COLUMNS = [{"key": key, "label": key} for key in ["status", "id", "runs", "m"]]
ROW = {"status": "passed", "id": "inv/r1", "m": "a"}


@pytest.fixture(autouse=True)
def format_cell() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.tui.run_cells.format_cell",
        side_effect=lambda key, value: f"{key}={value}",
    ) as found:
        yield found


def test_formats_each_column_from_the_row() -> None:
    assert run_cells(ROW, COLUMNS) == ["status=passed", "id=inv/r1", "", "m=a"]


def test_leaves_a_column_missing_from_the_row_blank() -> None:
    assert run_cells({}, COLUMNS) == ["", "", "", ""]
