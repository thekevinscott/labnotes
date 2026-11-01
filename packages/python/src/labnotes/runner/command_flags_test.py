import pytest

from labnotes.runner.command_flags import CommandFlag, command_flags


def spans(command: str) -> list[tuple[str, str, bool]]:
    return [
        (flag.name, command[flag.start : flag.end], flag.joined)
        for flag in command_flags(command)
    ]


def test_finds_a_flag_and_its_value() -> None:
    assert command_flags("run --memory 8g") == [CommandFlag("memory", 4, 15, False)]


def test_finds_a_flag_joined_to_its_value() -> None:
    assert command_flags("run --memory=8g x") == [CommandFlag("memory", 4, 15, True)]


@pytest.mark.parametrize(
    ("command", "found"),
    [
        ("run --dry-run", [("dry-run", "--dry-run", False)]),
        ("run --a --b 1", [("a", "--a", False), ("b", "--b 1", False)]),
        ("run --a -v", [("a", "--a", False)]),
        ("run --a  'x y' z", [("a", "--a  'x y'", False)]),
        ('run --a "x \\" y"', [("a", '--a "x \\" y"', False)]),
        ("run --a x\\ y", [("a", "--a x\\ y", False)]),
        ("run --a x\\; y", [("a", "--a x\\;", False)]),
        ("run --a=x y", [("a", "--a=x", True)]),
        ("run --a='x y' z", [("a", "--a='x y'", True)]),
        ("run --a && b", [("a", "--a", False)]),
        ("run --a; b", [("a", "--a", False)]),
        ("run --a|b", [("a", "--a", False)]),
        ("run --a >log", [("a", "--a", False)]),
        ("run --a (b)", [("a", "--a", False)]),
        ("run --a <in", [("a", "--a", False)]),
        ("x --a 1 && y --b 2", [("a", "--a 1", False), ("b", "--b 2", False)]),
        ("run -a 1 -- x", []),
        ("run '--a' x", []),
        ("run a--b x", []),
    ],
)
def test_finds_the_flags(command: str, found: list[tuple[str, str, bool]]) -> None:
    assert spans(command) == found


def test_reads_a_backslash_newline_as_one_word() -> None:
    assert spans("run --a x\\\ny") == [("a", "--a x\\\ny", False)]
