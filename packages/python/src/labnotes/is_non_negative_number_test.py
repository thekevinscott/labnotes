import math

import pytest

from labnotes.is_non_negative_number import is_non_negative_number


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True),
        (2, True),
        (0.5, True),
        (0.0, True),
        (-1, False),
        (-0.5, False),
        (False, False),
        (True, False),
        ("2", False),
        (math.inf, False),
        (math.nan, False),
    ],
)
def test_accepts_only_finite_numbers_from_zero(value: object, expected: bool) -> None:
    assert is_non_negative_number(value) is expected
