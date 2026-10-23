from typing import Any
from unittest import mock

from labnotes.view.answer import answer

REQUEST = {
    "columns": [{"key": "id", "label": "id"}],
    "rows": {"runs/a": {"id": "a"}, "runs/b": {"id": "b"}},
}


def runs(columns: list[Any]) -> tuple[list[Any], Any]:
    return [*columns, "model"], lambda row: {**row, "model": f"m-{row['id']}"}


def test_answers_with_the_columns_and_a_row_per_run() -> None:
    assert answer(runs, REQUEST) == {
        "columns": [{"key": "id", "label": "id"}, "model"],
        "rows": {
            "runs/a": {"id": "a", "model": "m-a"},
            "runs/b": {"id": "b", "model": "m-b"},
        },
    }


def test_passes_the_native_columns_to_the_function() -> None:
    build = mock.Mock(return_value=([], lambda row: row))

    answer(build, REQUEST)

    build.assert_called_once_with(REQUEST["columns"])
