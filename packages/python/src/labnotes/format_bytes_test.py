import pytest

from labnotes.format_bytes import format_bytes


@pytest.mark.parametrize(
    ("count", "shown"),
    [
        (None, ""),
        (0, "0 B"),
        (999, "999 B"),
        (1000, "1.0 KB"),
        (1_000_000, "1.0 MB"),
        (1_700_000, "1.7 MB"),
        (3_249_999_999, "3.2 GB"),
        (5_200_000_000_000, "5.2 TB"),
        (5_200_000_000_000_000, "5200.0 TB"),
    ],
)
def test_formats_a_byte_count(count: int | None, shown: str) -> None:
    assert format_bytes(count) == shown
