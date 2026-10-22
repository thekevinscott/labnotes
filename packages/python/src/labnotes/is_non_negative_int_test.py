import pytest

from labnotes.is_non_negative_int import is_non_negative_int


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, True), (2, True), (-1, False), (False, False), ("2", False), (1.0, False)],
)
def test_accepts_only_whole_numbers_from_zero(value: object, expected: bool) -> None:
    assert is_non_negative_int(value) is expected
