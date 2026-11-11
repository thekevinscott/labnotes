import pytest

from labnotes.visible_line import visible_line


@pytest.mark.parametrize(
    ("line", "shown"),
    [
        ("plain", "plain"),
        ("", ""),
        ("crlf\r", "crlf"),
        ("step 1\rstep 2\r", "step 2"),
        ("step 1\rstep 2", "step 2"),
        ("a\rb\rc", "c"),
        ("done\r\r", "done"),
        ("\r", ""),
    ],
)
def test_keeps_the_last_non_empty_overwrite(line: str, shown: str) -> None:
    assert visible_line(line) == shown
