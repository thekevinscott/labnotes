from labnotes.runner.group_args import Arg, group_args


def test_groups_flags_with_their_values() -> None:
    assert group_args(["--a", "1", "--b=2", "--c", "--d", "-v", "x", "--e"]) == [
        Arg("a", "1", ["--a", "1"]),
        Arg("b", "2", ["--b=2"]),
        Arg("c", None, ["--c"]),
        Arg("d", None, ["--d"]),
        Arg(None, None, ["-v"]),
        Arg(None, None, ["x"]),
        Arg("e", None, ["--e"]),
    ]


def test_keeps_equals_signs_in_the_value() -> None:
    assert group_args(["--a=b=c"]) == [Arg("a", "b=c", ["--a=b=c"])]


def test_keeps_an_empty_value() -> None:
    assert group_args(["--a=", "--b", ""]) == [
        Arg("a", "", ["--a="]),
        Arg("b", "", ["--b", ""]),
    ]


def test_groups_nothing() -> None:
    assert group_args([]) == []
