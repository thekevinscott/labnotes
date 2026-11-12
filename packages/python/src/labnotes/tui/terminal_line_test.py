import pytest

from labnotes.tui.terminal_line import terminal_line


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("plain", "plain"),
        ("", ""),
        ("crlf line\r", "crlf line"),
        ("step 0\rstep 1\rstep 2\r", "step 2"),
        ("\rprogress 50%", "progress 50%"),
        ("\r\r", ""),
        ("\x1b[31mred\x1b[0m\r", "\x1b[31mred\x1b[0m"),
        ("\x1b]0;my title\x07hello", "hello"),
        ("a\x1b]2;t\x07b\x1b]0;u\x07c", "abc"),
        ("shown\r\x1b]0;title\x07", "shown"),
        ("\x1b]\x07empty title", "empty title"),
    ],
)
def test_shows_what_a_terminal_would(raw: str, shown: str) -> None:
    assert terminal_line(raw) == shown
