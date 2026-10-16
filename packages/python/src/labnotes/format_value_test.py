import pytest

from labnotes.format_value import format_value


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (None, "—"),
        (True, "true"),
        (False, "false"),
        ({"a": 1}, '{"a": 1}'),
        ([1, 2], "[1, 2]"),
        (12, "12"),
        ("opus", "opus"),
    ],
)
def test_formats_values_for_display(value: object, shown: str) -> None:
    assert format_value(value) == shown
