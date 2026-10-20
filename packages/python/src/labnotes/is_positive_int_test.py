import pytest

from labnotes.is_positive_int import is_positive_int


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, True), (3, True), (0, False), (-1, False), (True, False), ("2", False)],
)
def test_accepts_only_positive_integers(value: object, expected: bool) -> None:
    assert is_positive_int(value) is expected
