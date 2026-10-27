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
        2,
    )

    assert (config.name, config.command, config.repeats, config.params) == (
        "Study",
        "run",
        3,
        {"m": ["a", "b"]},
    )


def test_defaults_to_one_repeat_and_no_params() -> None:
    config = read_experiment_config(PATH, 'command = "run"\n', "adhoc", 1, 2)

    assert (
        config.name,
        config.repeats,
        config.params,
        config.counts,
        config.mode,
        config.concurrency,
        config.retries,
        config.meta,
        config.memory_interval,
    ) == (None, 1, {}, "default", "adhoc", 1, 2, None, 5.0)


def test_falls_back_to_the_project_mode_concurrency_and_retries() -> None:
    config = read_experiment_config(PATH, 'command = "run"\n', "matrix", 3, 5)

    assert (config.mode, config.concurrency, config.retries) == ("matrix", 3, 5)


@pytest.mark.parametrize("retries", [0, 3])
def test_reads_retries_over_the_project_retries(retries: int) -> None:
    config = read_experiment_config(
        PATH, f'command = "run"\nretries = {retries}\n', "adhoc", 1, 2
    )

    assert config.retries == retries


@pytest.mark.parametrize("interval", [0, 2, 0.5])
def test_reads_the_memory_interval(interval: float) -> None:
    config = read_experiment_config(
        PATH, f'command = "run"\nmemory_interval = {interval}\n', "adhoc", 1, 2
    )

    assert config.memory_interval == interval


def test_layers_the_memory_interval_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH, "", "adhoc", 1, 2, {"command": "run", "memory_interval": 30}
    )

    assert config.memory_interval == 30


def test_reads_concurrency_over_the_project_concurrency() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\nconcurrency = 2\n', "adhoc", 3, 2
    )

    assert config.concurrency == 2


def test_reads_counts() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\ncounts = "exit_code = 0"\n', "adhoc", 1, 2
    )

    assert config.counts == "exit_code = 0"


def test_reads_meta() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\nmeta = "uv run meta.py"\n', "adhoc", 1, 2
    )

    assert config.meta == "uv run meta.py"


def test_layers_meta_from_the_defaults() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\n', "adhoc", 1, 2, {"meta": "git rev-parse HEAD"}
    )

    assert config.meta == "git rev-parse HEAD"


@pytest.mark.parametrize(
    ("mode", "project"), [("matrix", "adhoc"), ("adhoc", "matrix")]
)
def test_reads_mode_over_the_project_mode(mode: str, project: str) -> None:
    config = read_experiment_config(
        PATH, f'command = "run"\nmode = "{mode}"\n', project, 1, 2
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
        ('command = "run"\nmeta = 1\n', "meta must be a string"),
        ('command = "run"\nmeta = " "\n', "meta must be a string"),
        ('command = "run"\ncounts = 1\n', "counts must be a SQL condition"),
        ('command = "run"\ncounts = " "\n', "counts must be a SQL condition"),
        ('command = "run"\nmode = "once"\n', "mode must be matrix or adhoc"),
        ('command = "run"\nconcurrency = 0\n', "concurrency must be a positive"),
        ('command = "run"\nretries = -1\n', "retries must be 0 or more"),
        ('command = "run"\nretries = true\n', "retries must be 0 or more"),
        ('command = "run"\nmemory_interval = -1\n', "memory_interval must be"),
        ('command = "run"\nmemory_interval = true\n', "memory_interval must be"),
        ('command = "run"\nmemory_interval = "5"\n', "memory_interval must be"),
        ('command = "run"\nmemory_interval = inf\n', "memory_interval must be"),
        ('command = "run"\nviews = 1\n', "views must be a table"),
        ('command = "run"\n[views]\nrun = "x"\n', "unknown keys in views: run"),
        ('command = "run"\n[views]\nruns = 1\n', "views.runs must be a command"),
        ('command = "run"\n[views]\nruns = " "\n', "views.runs must be a command"),
    ],
)
def test_rejects_a_bad_config(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as error:
        read_experiment_config(PATH, text, "adhoc", 1, 2)

    assert str(error.value).startswith(f"{PATH}: ")


@pytest.mark.parametrize(
    "source",
    ['command = "run"\n[views]\nruns = "view"\n', 'command = "run"\n[views]\n'],
)
def test_accepts_views(source: str) -> None:
    read_experiment_config(PATH, source, "adhoc", 1, 2)


def test_validates_the_config_layered_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH,
        '[params]\nm = ["b"]\n',
        "adhoc",
        1,
        2,
        {"command": "run", "params": {"m": ["a"], "n": [1]}},
    )

    assert (config.command, config.params) == ("run", {"m": ["b"], "n": [1]})


@pytest.mark.parametrize(("source", "retries"), [("", 4), ("retries = 0\n", 0)])
def test_layers_retries_over_the_defaults(source: str, retries: int) -> None:
    config = read_experiment_config(
        PATH, source, "adhoc", 1, 2, {"command": "run", "retries": 4}
    )

    assert config.retries == retries


@pytest.mark.parametrize(
    ("defaults", "message"),
    [
        ({"repeats": 0}, "repeats must be a positive integer"),
        ({"retries": -1}, "retries must be 0 or more"),
    ],
)
def test_rejects_a_bad_default(defaults: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_experiment_config(PATH, 'command = "run"\n', "adhoc", 1, 2, defaults)


def test_reads_setup_and_teardown() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\nsetup = "up"\nteardown = "down"\n', "adhoc", 1, 2
    )

    assert (config.setup, config.teardown) == ("up", "down")


def test_has_no_setup_or_teardown_by_default() -> None:
    config = read_experiment_config(PATH, 'command = "run"\n', "adhoc", 1, 2)

    assert (config.setup, config.teardown) == (None, None)


def test_prefers_the_experiment_hooks_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH,
        'command = "run"\nsetup = "mine"\n',
        "adhoc",
        1,
        2,
        {"setup": "shared", "teardown": "shared down"},
    )

    assert (config.setup, config.teardown) == ("mine", "shared down")


def test_merges_environment_keys_with_the_experiment_winning() -> None:
    config = read_experiment_config(
        PATH,
        'command = "run"\n[env]\nBOTH = "own"\nOWN = "second"\n',
        "adhoc",
        1,
        2,
        {"env": {"BASE": "first", "BOTH": "shared"}},
    )
    assert config.env == {"BASE": "first", "BOTH": "own", "OWN": "second"}


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('command = "run"\nenv = 3\n', "env must be a table"),
        ('command = "run"\n[env]\nFOO = 3\n', "env.FOO must be a string"),
        ('command = "run"\n[env]\nFOO = true\n', "env.FOO must be a string"),
        (
            'command = "run"\n[env]\nLABNOTES_RUN = "wrong"\n',
            "env.LABNOTES_RUN is reserved",
        ),
    ],
)
def test_rejects_invalid_environment_values(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_experiment_config(PATH, source, "adhoc", 1, 2)


@pytest.mark.parametrize("hook", ["setup", "teardown"])
@pytest.mark.parametrize("value", ['""', '"  "', "3"])
def test_rejects_a_hook_that_is_not_a_command(hook: str, value: str) -> None:
    with pytest.raises(ValueError) as error:
        read_experiment_config(
            PATH, f'command = "run"\n{hook} = {value}\n', "adhoc", 1, 2
        )

    assert str(error.value) == f"{PATH}: {hook} must be a string"
