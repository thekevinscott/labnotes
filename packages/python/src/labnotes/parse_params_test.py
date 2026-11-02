import pytest

from labnotes.parse_params import parse_params


def test_groups_values_by_name_in_order() -> None:
    assert parse_params(["model=opus", "size=3", "model=a=b"]) == {
        "model": ["opus", "a=b"],
        "size": [3],
    }


def test_takes_nothing() -> None:
    assert parse_params([]) == {}


@pytest.mark.parametrize("pair", ["model", "=opus"])
def test_rejects_a_pair_without_a_name_and_value(pair: str) -> None:
    with pytest.raises(ValueError, match=f"--param {pair} must look like NAME=VALUE"):
        parse_params([pair])
