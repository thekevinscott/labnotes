import pytest

from labnotes.parse_subset import parse_subset


def test_reads_each_param() -> None:
    assert parse_subset(["--model=small", "--lang=en"]) == {
        "model": ["small"],
        "lang": ["en"],
    }


def test_reads_nothing() -> None:
    assert parse_subset([]) == {}


def test_keeps_equals_signs_in_the_value() -> None:
    assert parse_subset(["--expr=a=b"]) == {"expr": ["a=b"]}


def test_allows_an_empty_value() -> None:
    assert parse_subset(["--model="]) == {"model": [""]}


@pytest.mark.parametrize("arg", ["model=small", "--model", "--=small", "-m=small"])
def test_needs_param_equals_value(arg: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_subset([arg])
    assert str(error.value) == f"Unexpected {arg}. Pick params with --PARAM=VALUE."


def test_collects_repeated_params_in_order() -> None:
    assert parse_subset(["--model=large", "--lang=en", "--model=small"]) == {
        "model": ["large", "small"],
        "lang": ["en"],
    }


def test_keeps_commas_in_the_value() -> None:
    assert parse_subset(["--model=a,b"]) == {"model": ["a,b"]}
