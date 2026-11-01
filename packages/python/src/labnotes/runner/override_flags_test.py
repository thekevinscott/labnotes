import pytest

from labnotes.runner.override_flags import override_flags


@pytest.mark.parametrize(
    ("command", "args", "result"),
    [
        ("s --m 8g --o x", ["--m", "24g"], "s --m 24g --o x"),
        ("s --m 8g --o x", ["--m=24g"], "s --m 24g --o x"),
        ("s --m=8g --o x", ["--m", "24g"], "s --m=24g --o x"),
        ("s --m=8g --o x", ["--m=24g"], "s --m=24g --o x"),
        ("s --v --o x", ["--v", "1"], "s --v 1 --o x"),
        ("s --m 8g", ["--m", "a b"], "s --m 'a b'"),
        ("s --m=8g", ["--m=a b"], "s --m='a b'"),
        ("s --a 1 --b 2", ["--b", "3", "--a", "4"], "s --a 4 --b 3"),
        (
            "s --a 1 --b 2",
            ["--a", "long value", "--b", "3"],
            "s --a 'long value' --b 3",
        ),
    ],
)
def test_replaces_the_value_in_place(
    command: str, args: list[str], result: str
) -> None:
    assert override_flags(command, args) == (result, [])


def test_returns_args_the_command_lacks() -> None:
    assert override_flags("s --m 8g", ["x", "--auth", "api", "--m", "1", "-v"]) == (
        "s --m 1",
        ["x", "--auth", "api", "-v"],
    )


def test_leaves_a_flag_already_set_when_given_without_a_value() -> None:
    assert override_flags("s --dry-run --m 8g", ["--dry-run", "--m"]) == (
        "s --dry-run --m 8g",
        [],
    )


def test_leaves_the_command_alone_without_args() -> None:
    assert override_flags("s --m 8g", []) == ("s --m 8g", [])
