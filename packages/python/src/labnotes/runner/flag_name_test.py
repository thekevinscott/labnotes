import pytest

from labnotes.runner.flag_name import flag_name


@pytest.mark.parametrize(
    ("token", "name"),
    [
        ("--auth", "auth"),
        ("--auth=api", "auth"),
        ("--", None),
        ("--=x", None),
        ("-v", None),
        ("auth", None),
    ],
)
def test_names_the_flag(token: str, name: str | None) -> None:
    assert flag_name(token) == name
