import pytest

from labnotes.parse_param_value import parse_param_value


@pytest.mark.parametrize(
    ("value", "parsed"),
    [
        ("3", 3),
        ("0.5", 0.5),
        ("true", True),
        ('"3"', "3"),
        ("[1, 2]", [1, 2]),
        ("opus", "opus"),
        ("en,fr", "en,fr"),
        ("", ""),
        ("a = b", "a = b"),
    ],
)
def test_parses_toml_or_keeps_the_string(value: str, parsed: object) -> None:
    assert parse_param_value(value) == parsed
