from collections.abc import Iterator
from pathlib import Path

from unittest import mock

import pytest

from labnotes.runner.read_experiment_config import read_experiment_config


@pytest.fixture(autouse=True)
def default_counts() -> Iterator[None]:
    with mock.patch("labnotes.runner.read_experiment_config.DEFAULT_COUNTS", "default"):
        yield


PATH = Path("/p/experiment.toml")


def test_reads_command_repeats_and_params() -> None:
    config = read_experiment_config(
        PATH,
        'name = "Study"\ncommand = "run"\nrepeats = 3\n[params]\nm = ["a", "b"]\n',
        "adhoc",
        1,
    )

    assert (config.name, config.command, config.repeats, config.params) == (
        "Study",
        "run",
        3,
        {"m": ["a", "b"]},
    )


def test_defaults_to_one_repeat_and_no_params() -> None:
    config = read_experiment_config(PATH, 'command = "run"\n', "adhoc", 1)

    assert (
        config.name,
        config.repeats,
        config.params,
        config.counts,
        config.mode,
        config.concurrency,
    ) == (None, 1, {}, "default", "adhoc", 1)


def test_falls_back_to_the_project_mode_and_concurrency() -> None:
    config = read_experiment_config(PATH, 'command = "run"\n', "matrix", 3)

    assert (config.mode, config.concurrency) == ("matrix", 3)


def test_reads_concurrency_over_the_project_concurrency() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\nconcurrency = 2\n', "adhoc", 3
    )

    assert config.concurrency == 2


def test_reads_counts() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\ncounts = "exit_code = 0"\n', "adhoc", 1
    )

    assert config.counts == "exit_code = 0"


@pytest.mark.parametrize(
    ("mode", "project"), [("matrix", "adhoc"), ("adhoc", "matrix")]
)
def test_reads_mode_over_the_project_mode(mode: str, project: str) -> None:
    config = read_experiment_config(
        PATH, f'command = "run"\nmode = "{mode}"\n', project, 1
    )

    assert config.mode == mode


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("command = ", "Invalid"),
        ('command = "run"\nn = 2\n', "unknown keys n"),
        ("repeats = 2\n", "command must be a string"),
        ('name = 1\ncommand = "run"\n', "name must be a string"),
        ('name = " "\ncommand = "run"\n', "name must be a string"),
        ('command = " "\n', "command must be a string"),
        ('command = "run"\nrepeats = 0\n', "repeats must be a positive integer"),
        ('command = "run"\nrepeats = true\n', "repeats must be a positive integer"),
        ('command = "run"\nparams = 1\n', "params must be a table"),
        ('command = "run"\n[params]\nm = "a"\n', "params.m must be a non-empty list"),
        ('command = "run"\n[params]\nm = []\n', "params.m must be a non-empty list"),
        ('command = "run"\n[params]\nd = [1979-05-27]\n', "dates or times"),
        ('command = "run"\ncounts = 1\n', "counts must be a SQL condition"),
        ('command = "run"\ncounts = " "\n', "counts must be a SQL condition"),
        ('command = "run"\nmode = "once"\n', "mode must be matrix or adhoc"),
        ('command = "run"\nconcurrency = 0\n', "concurrency must be a positive"),
    ],
)
def test_rejects_a_bad_config(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as error:
        read_experiment_config(PATH, text, "adhoc", 1)

    assert str(error.value).startswith(f"{PATH}: ")


def test_validates_the_config_layered_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH,
        '[params]\nm = ["b"]\n',
        "adhoc",
        1,
        {"command": "run", "params": {"m": ["a"], "n": [1]}},
    )

    assert (config.command, config.params) == ("run", {"m": ["b"], "n": [1]})


def test_rejects_a_bad_default() -> None:
    with pytest.raises(ValueError, match="repeats must be a positive integer"):
        read_experiment_config(PATH, 'command = "run"\n', "adhoc", 1, {"repeats": 0})
