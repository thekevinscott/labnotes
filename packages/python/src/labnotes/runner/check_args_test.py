import pytest

from labnotes.runner.check_args import check_args

PARAMS: dict[str, list[object]] = {"model": ["small", "large"]}


def test_accepts_new_flags() -> None:
    check_args(PARAMS, "study --out {run_dir}", ["--auth", "api", "--dry-run"])


def test_accepts_plain_values() -> None:
    check_args(PARAMS, "study --out x", ["model", "out", "-v", "--"])


@pytest.mark.parametrize("command", ["study --out x", "study --out=x"])
def test_accepts_a_flag_already_in_the_command(command: str) -> None:
    check_args(PARAMS, command, ["--out=y"])


def test_accepts_a_new_flag_given_twice() -> None:
    check_args(PARAMS, "study --out x", ["--tag", "a", "--tag", "b"])


def test_rejects_a_param() -> None:
    with pytest.raises(
        ValueError, match=r"^--model is a param\. Pick it with --model=VALUE\.$"
    ):
        check_args(PARAMS, "study", ["--model", "large"])


def test_rejects_a_param_given_with_equals() -> None:
    with pytest.raises(ValueError, match=r"^--model is a param\."):
        check_args(PARAMS, "study", ["--model=large"])


def test_rejects_a_param_even_in_the_command() -> None:
    with pytest.raises(ValueError, match=r"^--model is a param\."):
        check_args(PARAMS, "study --model x --model y", ["--model=large"])


def test_rejects_a_flag_the_command_repeats() -> None:
    with pytest.raises(
        ValueError,
        match=r"^--out is in the command more than once, so -- can't override it\.$",
    ):
        check_args(PARAMS, "study --out x --out=y", ["--out", "z"])


def test_rejects_an_override_given_twice() -> None:
    with pytest.raises(ValueError, match=r"^--out is in -- ARGS more than once\.$"):
        check_args(PARAMS, "study --out x", ["--out", "y", "--out=z"])
