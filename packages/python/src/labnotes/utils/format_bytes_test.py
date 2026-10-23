from unittest import mock

from labnotes.utils.format_bytes import format_bytes


def test_shows_nothing_for_an_unknown_count() -> None:
    with mock.patch("labnotes.utils.format_bytes.decimal") as decimal:
        assert format_bytes(None) == ""
    decimal.assert_not_called()


def test_shows_a_count_in_decimal_units() -> None:
    with mock.patch(
        "labnotes.utils.format_bytes.decimal", return_value="3.2 GB"
    ) as decimal:
        assert format_bytes(3_249_999_999) == "3.2 GB"
    decimal.assert_called_once_with(3_249_999_999)
