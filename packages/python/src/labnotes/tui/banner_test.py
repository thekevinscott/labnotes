import pytest

from labnotes.tui.banner import Banner

LINE = "\x1b[2m── invocation 2 ──\x1b[0m".encode()


def test_takes_one_row() -> None:
    banner = Banner("invocation 2")
    assert (banner.label, banner.lines, banner.rows) == ("invocation 2", 1, 1)


@pytest.mark.parametrize(
    ("first", "count", "found"),
    [(0, 1, [LINE]), (0, 5, [LINE]), (0, 0, []), (1, 1, [])],
)
def test_reads_its_label_as_one_dim_line(
    first: int, count: int, found: list[bytes]
) -> None:
    assert Banner("invocation 2").read(first, count) == found
