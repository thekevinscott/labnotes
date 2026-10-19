from collections.abc import Iterator
from pathlib import Path

from unittest import mock

import pytest

from labnotes.runner.read_experiment_config import read_experiment_config


@pytest.fixture(autouse=True)
def default_counts() -> Iterator[None]:
    with mock.patch("labnotes.runner.read_experiment_config.DEFAULT_COUNTS", "default"):
        yield


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "experiment.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_command_repeats_and_params(tmp_path: Path) -> None:
    config = read_experiment_config(
        write(
            tmp_path,
            'name = "Study"\ncommand = "run"\nrepeats = 3\n[params]\nm = ["a", "b"]\n',
        )
    )

    assert (config.name, config.command, config.repeats, config.params) == (
        "Study",
        "run",
        3,
        {"m": ["a", "b"]},
    )


def test_defaults_to_one_repeat_and_no_params(tmp_path: Path) -> None:
    config = read_experiment_config(write(tmp_path, 'command = "run"\n'))

    assert (
        config.name,
        config.repeats,
        config.params,
        config.counts,
        config.mode,
    ) == (None, 1, {}, "default", "fill")


def test_reads_counts(tmp_path: Path) -> None:
    config = read_experiment_config(
        write(tmp_path, 'command = "run"\ncounts = "exit_code = 0"\n')
    )

    assert config.counts == "exit_code = 0"


@pytest.mark.parametrize("mode", ["fill", "adhoc"])
def test_reads_mode(tmp_path: Path, mode: str) -> None:
    config = read_experiment_config(
        write(tmp_path, f'command = "run"\nmode = "{mode}"\n')
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
        ('command = "run"\nmode = "once"\n', "mode must be fill or adhoc"),
    ],
)
def test_rejects_a_bad_config(tmp_path: Path, text: str, message: str) -> None:
    path = write(tmp_path, text)

    with pytest.raises(ValueError, match=message) as error:
        read_experiment_config(path)

    assert str(error.value).startswith(f"{path}: ")
