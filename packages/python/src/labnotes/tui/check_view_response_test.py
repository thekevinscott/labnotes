import json
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest

from labnotes.tui.check_view_response import check_view_response

REQUEST = {
    "columns": [{"key": "id", "label": "id"}],
    "rows": {"runs/a": {"id": "a", "folder": "runs/a"}},
}


@pytest.fixture(autouse=True)
def view_column() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.tui.check_view_response.view_column",
        side_effect=lambda entry: (
            {"key": entry, "label": entry} if isinstance(entry, str) else entry
        ),
    ) as found:
        yield found


def check(response: object) -> tuple[list[dict[str, str]], dict[str, Any]]:
    return check_view_response(json.dumps(response), REQUEST)


def test_reads_columns_and_rows() -> None:
    columns, rows = check(
        {
            "columns": [{"key": "id", "label": "Run"}, "m", "x"],
            "rows": {"runs/a": {"id": "a", "m": 1, "folder": "runs/a"}},
        }
    )

    assert columns == [
        {"key": "id", "label": "Run"},
        {"key": "m", "label": "m"},
        {"key": "x", "label": "x"},
    ]
    assert rows == {"runs/a": {"id": "a", "m": 1, "folder": "runs/a"}}


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ([], "the response must be an object with columns and rows"),
        ({"columns": []}, "the response must be an object with columns and rows"),
        (
            {"columns": [], "rows": {}, "x": 1},
            "the response must be an object with columns and rows",
        ),
        ({"columns": {}, "rows": {}}, "columns must be a list"),
        ({"columns": ["m", {"key": "m"}], "rows": {}}, "column m is listed twice"),
        ({"columns": [], "rows": []}, "rows must be an object"),
        ({"columns": [], "rows": {}}, "no row for runs/a"),
        (
            {"columns": [], "rows": {"runs/a": {}, "runs/b": {}}},
            "a row for runs/b, which wasn't asked for",
        ),
        ({"columns": [], "rows": {"runs/a": 1}}, "runs/a: the row must be an object"),
        (
            {"columns": [], "rows": {"runs/a": {"x": 1, "y": 2}}},
            "runs/a: unknown columns x, y",
        ),
    ],
)
def test_rejects_a_bad_response(response: object, message: str) -> None:
    with pytest.raises(ValueError) as error:
        check(response)

    assert str(error.value) == message


def test_lets_rows_keep_native_values_that_arent_columns() -> None:
    _, rows = check({"columns": [], "rows": {"runs/a": {"id": "a"}}})

    assert rows == {"runs/a": {"id": "a"}}


def test_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="^invalid JSON: Expecting value"):
        check_view_response("nope\n", REQUEST)


def test_reads_each_column(view_column: mock.MagicMock) -> None:
    check({"columns": ["m", {"key": "id"}], "rows": {"runs/a": {}}})

    assert view_column.call_args_list == [mock.call("m"), mock.call({"key": "id"})]


def test_passes_on_a_bad_column(view_column: mock.MagicMock) -> None:
    view_column.side_effect = ValueError("a column needs a string key")

    with pytest.raises(ValueError, match="^a column needs a string key$"):
        check({"columns": [1], "rows": {"runs/a": {}}})
