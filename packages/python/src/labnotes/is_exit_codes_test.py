import pytest

from labnotes.is_exit_codes import is_exit_codes


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([], True),
        ([1, 75, 255], True),
        ([0], False),
        ([256], False),
        ([True], False),
        (["1"], False),
        (1, False),
    ],
)
def test_accepts_a_list_of_failing_exit_codes(value: object, expected: bool) -> None:
    assert is_exit_codes(value) is expected
