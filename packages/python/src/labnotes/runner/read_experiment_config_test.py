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
        'name = "Study"\ncommand = "run"\ncontinues = false\nrepeats = 3\n[params]\nm = ["a", "b"]\n',
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
    config = read_experiment_config(PATH, 'command = "run"\ncontinues = false\n', 1, 2)

    assert (
        config.name,
        config.repeats,
        config.params,
        config.counts,
        config.concurrency,
        config.retries,
        config.meta,
        config.memory_interval,
    ) == (None, 1, {}, "default", 1, 2, None, 5.0)


@pytest.mark.parametrize("continues", [False, True])
def test_reads_continues(continues: bool) -> None:
    config = read_experiment_config(
        PATH, f'command = "run"\ncontinues = {str(continues).lower()}\n', 1, 2
    )

    assert config.continues is continues


def test_takes_continues_from_the_defaults() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\n', 1, 2, {"continues": True}
    )

    assert config.continues is True


def test_requires_continues() -> None:
    with pytest.raises(ValueError, match="continues is required") as error:
        read_experiment_config(PATH, 'command = "run"\n', 1, 2)

    assert "migrations.d" in str(error.value)


@pytest.mark.parametrize(
    ("source", "defaults"),
    [
        ('command = "run"\ncontinues = false\nmode = "adhoc"\n', {}),
        ('command = "run"\ncontinues = false\n', {"mode": "matrix"}),
    ],
)
def test_rejects_mode(source: str, defaults: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="mode was removed") as error:
        read_experiment_config(PATH, source, 1, 2, defaults)

    assert "migrations.d" in str(error.value)


def test_falls_back_to_the_project_concurrency_and_retries() -> None:
    config = read_experiment_config(PATH, 'command = "run"\ncontinues = false\n', 3, 5)

    assert (config.concurrency, config.retries) == (3, 5)


def test_falls_back_to_the_project_resumes() -> None:
    source = 'command = "run"\ncontinues = false\n'

    assert read_experiment_config(PATH, source, 1, 2).resumes == 3
    assert read_experiment_config(PATH, source, 1, 2, None, 7).resumes == 7


@pytest.mark.parametrize("resumes", [0, 4])
def test_reads_resumes_over_the_project_resumes(resumes: int) -> None:
    config = read_experiment_config(
        PATH,
        f'command = "run"\ncontinues = false\nresumes = {resumes}\n',
        1,
        2,
        None,
        7,
    )

    assert config.resumes == resumes


@pytest.mark.parametrize("retries", [0, 3])
def test_reads_retries_over_the_project_retries(retries: int) -> None:
    config = read_experiment_config(
        PATH,
        f'command = "run"\ncontinues = false\nretries = {retries}\n',
        1,
        2,
    )

    assert config.retries == retries


@pytest.mark.parametrize("interval", [0, 2, 0.5])
def test_reads_the_memory_interval(interval: float) -> None:
    config = read_experiment_config(
        PATH,
        f'command = "run"\ncontinues = false\nmemory_interval = {interval}\n',
        1,
        2,
    )

    assert config.memory_interval == interval


def test_layers_the_memory_interval_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH, "", 1, 2, {"command": "run", "continues": False, "memory_interval": 30}
    )

    assert config.memory_interval == 30


def test_reads_concurrency_over_the_project_concurrency() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\ncontinues = false\nconcurrency = 2\n', 3, 2
    )

    assert config.concurrency == 2


def test_reads_counts() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\ncontinues = false\ncounts = "exit_code = 0"\n', 1, 2
    )

    assert config.counts == "exit_code = 0"


def test_reads_meta() -> None:
    config = read_experiment_config(
        PATH, 'command = "run"\ncontinues = false\nmeta = "uv run meta.py"\n', 1, 2
    )

    assert config.meta == "uv run meta.py"


def test_layers_meta_from_the_defaults() -> None:
    config = read_experiment_config(
        PATH,
        'command = "run"\ncontinues = false\n',
        1,
        2,
        {"meta": "git rev-parse HEAD"},
    )

    assert config.meta == "git rev-parse HEAD"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("command = ", "Invalid"),
        ('command = "run"\ncontinues = false\nn = 2\n', "unknown keys n"),
        ("repeats = 2\n", "command must be a string"),
        ('name = 1\ncommand = "run"\n', "name must be a string"),
        ('name = " "\ncommand = "run"\n', "name must be a string"),
        ('command = " "\n', "command must be a string"),
        (
            'command = "run"\ncontinues = false\nrepeats = 0\n',
            "repeats must be a positive integer",
        ),
        (
            'command = "run"\ncontinues = false\nrepeats = true\n',
            "repeats must be a positive integer",
        ),
        ('command = "run"\ncontinues = false\nparams = 1\n', "params must be a table"),
        (
            'command = "run"\ncontinues = false\n[params]\nm = "a"\n',
            "params.m must be a non-empty list",
        ),
        (
            'command = "run"\ncontinues = false\n[params]\nm = []\n',
            "params.m must be a non-empty list",
        ),
        (
            'command = "run"\ncontinues = false\n[params]\nd = [1979-05-27]\n',
            "dates or times",
        ),
        ('command = "run"\ncontinues = false\nmeta = 1\n', "meta must be a string"),
        ('command = "run"\ncontinues = false\nmeta = " "\n', "meta must be a string"),
        (
            'command = "run"\ncontinues = false\nfrom = 1\n',
            "from must be an experiment name",
        ),
        (
            'command = "run"\ncontinues = false\nfrom = " "\n',
            "from must be an experiment name",
        ),
        (
            'command = "run"\ncontinues = false\ncounts = 1\n',
            "counts must be a SQL condition",
        ),
        (
            'command = "run"\ncontinues = false\ncounts = " "\n',
            "counts must be a SQL condition",
        ),
        (
            'command = "run"\ncontinues = false\nconcurrency = 0\n',
            "concurrency must be a positive",
        ),
        (
            'command = "run"\ncontinues = false\nretries = -1\n',
            "retries must be 0 or more",
        ),
        (
            'command = "run"\ncontinues = false\nretries = true\n',
            "retries must be 0 or more",
        ),
        (
            'command = "run"\ncontinues = false\nresumes = -1\n',
            "resumes must be 0 or more",
        ),
        (
            'command = "run"\ncontinues = false\nresumes = true\n',
            "resumes must be 0 or more",
        ),
        (
            'command = "run"\ncontinues = false\nmemory_interval = -1\n',
            "memory_interval must be",
        ),
        (
            'command = "run"\ncontinues = false\nmemory_interval = true\n',
            "memory_interval must be",
        ),
        (
            'command = "run"\ncontinues = false\nmemory_interval = "5"\n',
            "memory_interval must be",
        ),
        (
            'command = "run"\ncontinues = false\nmemory_interval = inf\n',
            "memory_interval must be",
        ),
        ('command = "run"\ncontinues = false\nviews = 1\n', "views must be a table"),
        (
            'command = "run"\ncontinues = false\n[views]\nrun = "x"\n',
            'views.run must be "path/to/file.py:ClassName"',
        ),
        (
            'command = "run"\ncontinues = false\n[views]\nrun = 1\n',
            'views.run must be "path/to/file.py:ClassName"',
        ),
        (
            'command = "run"\ncontinues = false\n[views]\nrun = ":Run"\n',
            'views.run must be "path/to/file.py:ClassName"',
        ),
        (
            'command = "run"\ncontinues = false\n[views]\nrun = "run.py: "\n',
            'views.run must be "path/to/file.py:ClassName"',
        ),
        (
            'command = "run"\ncontinues = false\n[views]\n'
            + "".join(f'v{n} = "v.py:V"\n' for n in range(9)),
            "views holds at most 8 views besides runs",
        ),
        (
            'command = "run"\ncontinues = false\n[views]\nruns = 1\n',
            "views.runs must be a command",
        ),
        (
            'command = "run"\ncontinues = false\n[views]\nruns = " "\n',
            "views.runs must be a command",
        ),
        ('command = "run"\ncontinues = 1\n', "continues must be true or false"),
    ],
)
def test_rejects_a_bad_config(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as error:
        read_experiment_config(PATH, text, 1, 2)

    assert str(error.value).startswith(f"{PATH}: ")


@pytest.mark.parametrize(
    "source",
    [
        'command = "run"\ncontinues = false\n[views]\nruns = "view"\n',
        'command = "run"\ncontinues = false\n[views]\n',
        'command = "run"\ncontinues = false\n[views]\nruns = "view"\n'
        + "".join(f'v{n} = "views/v.py:V{n}"\n' for n in range(8)),
        'command = "run"\ncontinues = false\n[views]\nplot = "a:b.py:Plot"\n',
    ],
)
def test_accepts_views(source: str) -> None:
    read_experiment_config(PATH, source, 1, 2)


def test_accepts_the_experiment_it_came_from() -> None:
    source = 'from = "sanity-3"\ncommand = "run"\ncontinues = false\n'

    read_experiment_config(PATH, source, 1, 2)


def test_validates_the_config_layered_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH,
        '[params]\nm = ["b"]\n',
        1,
        2,
        {"command": "run", "continues": False, "params": {"m": ["a"], "n": [1]}},
    )

    assert (config.command, config.params) == ("run", {"m": ["b"], "n": [1]})


@pytest.mark.parametrize(("source", "retries"), [("", 4), ("retries = 0\n", 0)])
def test_layers_retries_over_the_defaults(source: str, retries: int) -> None:
    config = read_experiment_config(
        PATH, source, 1, 2, {"command": "run", "continues": False, "retries": 4}
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
        read_experiment_config(
            PATH, 'command = "run"\ncontinues = false\n', 1, 2, defaults
        )


def test_reads_setup_and_teardown() -> None:
    config = read_experiment_config(
        PATH,
        'command = "run"\ncontinues = false\nsetup = "up"\nteardown = "down"\n',
        1,
        2,
    )

    assert (config.setup, config.teardown) == ("up", "down")


def test_has_no_setup_or_teardown_by_default() -> None:
    config = read_experiment_config(PATH, 'command = "run"\ncontinues = false\n', 1, 2)

    assert (config.setup, config.teardown) == (None, None)


def test_prefers_the_experiment_hooks_over_the_defaults() -> None:
    config = read_experiment_config(
        PATH,
        'command = "run"\ncontinues = false\nsetup = "mine"\n',
        1,
        2,
        {"setup": "shared", "teardown": "shared down"},
    )

    assert (config.setup, config.teardown) == ("mine", "shared down")


def test_merges_environment_keys_with_the_experiment_winning() -> None:
    config = read_experiment_config(
        PATH,
        'command = "run"\ncontinues = false\n[env]\nBOTH = "own"\nOWN = "second"\n',
        1,
        2,
        {"env": {"BASE": "first", "BOTH": "shared"}},
    )
    assert config.env == {"BASE": "first", "BOTH": "own", "OWN": "second"}


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('command = "run"\ncontinues = false\nenv = 3\n', "env must be a table"),
        (
            'command = "run"\ncontinues = false\n[env]\nFOO = 3\n',
            "env.FOO must be a string",
        ),
        (
            'command = "run"\ncontinues = false\n[env]\nFOO = true\n',
            "env.FOO must be a string",
        ),
        (
            'command = "run"\ncontinues = false\n[env]\nLABNOTES_RUN = "wrong"\n',
            "env.LABNOTES_RUN is reserved",
        ),
    ],
)
def test_rejects_invalid_environment_values(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_experiment_config(PATH, source, 1, 2)


@pytest.mark.parametrize("hook", ["setup", "teardown"])
@pytest.mark.parametrize("value", ['""', '"  "', "3"])
def test_rejects_a_hook_that_is_not_a_command(hook: str, value: str) -> None:
    with pytest.raises(ValueError) as error:
        read_experiment_config(
            PATH,
            f'command = "run"\ncontinues = false\n{hook} = {value}\n',
            1,
            2,
        )

    assert str(error.value) == f"{PATH}: {hook} must be a string"
