import json
from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.print_rows import print_rows

ROWS: list[dict[str, object]] = [{"name": "a", "runs": 2, "last_run": None}]


@pytest.fixture
def rich() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.print_rows.Table") as table,
        mock.patch("labnotes.print_rows.Console") as console,
    ):
        yield {"Table": table, "Console": console}


def test_prints_json(
    capsys: pytest.CaptureFixture[str], rich: dict[str, mock.MagicMock]
) -> None:
    print_rows(ROWS, "json")

    assert json.loads(capsys.readouterr().out) == ROWS
    rich["Console"].assert_not_called()


def test_prints_a_table_with_blank_nulls(rich: dict[str, mock.MagicMock]) -> None:
    print_rows(ROWS, "table")

    rich["Table"].assert_called_once_with("name", "runs", "last_run")
    rich["Table"].return_value.add_row.assert_called_once_with("a", "2", "")
    rich["Console"].return_value.print.assert_called_once_with(
        rich["Table"].return_value
    )


def test_says_when_there_are_no_rows(
    capsys: pytest.CaptureFixture[str], rich: dict[str, mock.MagicMock]
) -> None:
    print_rows([], "table")

    assert capsys.readouterr().out == "No rows.\n"
