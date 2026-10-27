import pytest

from labnotes.runner.check_args import check_args

PARAMS: dict[str, list[object]] = {"model": ["small", "large"]}


def test_accepts_new_flags() -> None:
    check_args(PARAMS, "study --out {run_dir}", ["--auth", "api", "--dry-run"])


def test_accepts_plain_values() -> None:
    check_args(PARAMS, "study --out x", ["model", "out", "-v", "--"])


def test_rejects_a_param() -> None:
    with pytest.raises(
        ValueError, match=r"^--model is a param\. Pick it with --model=VALUE\.$"
    ):
        check_args(PARAMS, "study", ["--model", "large"])


def test_rejects_a_param_given_with_equals() -> None:
    with pytest.raises(ValueError, match=r"^--model is a param\."):
        check_args(PARAMS, "study", ["--model=large"])


@pytest.mark.parametrize("command", ["study --out x", "study --out=x"])
def test_rejects_a_flag_already_in_the_command(command: str) -> None:
    with pytest.raises(ValueError, match=r"^--out is already in the command\.$"):
        check_args(PARAMS, command, ["--out=y"])
