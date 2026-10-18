import pytest

from labnotes.tui.format_elapsed import format_elapsed


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, "0s"),
        (59.9, "59s"),
        (60, "1m 00s"),
        (125, "2m 05s"),
        (3599, "59m 59s"),
        (3600, "1h 00m"),
        (7380, "2h 03m"),
    ],
)
def test_formats_elapsed_time(seconds: float, text: str) -> None:
    assert format_elapsed(seconds) == text
