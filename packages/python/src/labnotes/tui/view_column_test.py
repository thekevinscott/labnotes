import pytest

from labnotes.tui.view_column import view_column


@pytest.mark.parametrize(
    ("entry", "column"),
    [
        ("x", {"key": "x", "label": "x"}),
        ({"key": "m"}, {"key": "m", "label": "m"}),
        ({"key": "id", "label": "Run"}, {"key": "id", "label": "Run"}),
        ({"key": "id", "label": ""}, {"key": "id", "label": ""}),
    ],
)
def test_reads_a_column(entry: object, column: dict[str, str]) -> None:
    assert view_column(entry) == column


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (1, "a column must be a string or an object"),
        ({}, "a column needs a string key"),
        ({"key": 1}, "a column needs a string key"),
        ({"key": "m", "label": 1}, "column m: label must be a string"),
        ({"key": "m", "width": 1, "align": 2}, "column m: unknown fields align, width"),
    ],
)
def test_rejects_a_bad_column(entry: object, message: str) -> None:
    with pytest.raises(ValueError) as error:
        view_column(entry)

    assert str(error.value) == message
