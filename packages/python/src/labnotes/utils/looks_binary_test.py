import pytest

from labnotes.utils.looks_binary import looks_binary


@pytest.mark.parametrize(
    ("head", "binary"),
    [
        (b"", False),
        (b"step 1\nstep 2\n", False),
        ("café\n".encode(), False),
        (b"caf\xc3", False),
        (b"text\x00more", True),
        (b"\x89PNG\r\n\x1a\n", True),
        (b"\xff\xfe", True),
    ],
)
def test_calls_a_head_binary_when_it_holds_nul_or_invalid_utf8(
    head: bytes, binary: bool
) -> None:
    assert looks_binary(head) is binary
