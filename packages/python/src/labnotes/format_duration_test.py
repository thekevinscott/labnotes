import pytest

from labnotes.format_duration import format_duration


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [(None, "—"), (0, "0s"), (500, "8m 20s"), (3720, "1h 02m")],
)
def test_formats_a_run_duration(seconds: int | None, shown: str) -> None:
    assert format_duration(seconds) == shown
