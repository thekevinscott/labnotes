from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.read_config import read_config


@pytest.fixture
def read_path() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.read_config.read_path", side_effect=lambda _, table, __, **___: table
    ) as read_path:
        yield read_path


def write(folder: Path, text: str) -> Path:
    path = folder / ".labnotes.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_each_table_path(tmp_path: Path, read_path: mock.MagicMock) -> None:
    path = write(tmp_path, '[runs]\npath = "x"\n')

    config = read_config(path)

    assert (config.experiments, config.files, config.runs) == (
        "experiments",
        "files",
        "runs",
    )
    assert read_path.call_args_list == [
        mock.call(path, "experiments", {}, single=False),
        mock.call(path, "files", {}, single=False),
        mock.call(path, "runs", {"path": "x"}, single=False),
    ]


def test_the_root_is_the_config_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read_path: mock.MagicMock
) -> None:
    write(tmp_path, "")
    monkeypatch.chdir(tmp_path)

    config = read_config(Path(".labnotes.toml"))

    assert (config.path, config.root) == (tmp_path / ".labnotes.toml", tmp_path)


@pytest.mark.parametrize(
    ("text", "mode"),
    [
        ("", "adhoc"),
        ("[experiments]\n", "adhoc"),
        ('[experiments]\nmode = "matrix"\n', "matrix"),
    ],
)
def test_reads_the_project_mode(
    tmp_path: Path, read_path: mock.MagicMock, text: str, mode: str
) -> None:
    assert read_config(write(tmp_path, text)).mode == mode


def test_rejects_an_unknown_mode(tmp_path: Path, read_path: mock.MagicMock) -> None:
    path = write(tmp_path, '[experiments]\nmode = "once"\n')

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == f"{path}: [experiments] mode must be matrix or adhoc"


@pytest.mark.parametrize(
    ("text", "concurrency"),
    [("", 1), ("[experiments]\nconcurrency = 4\n", 4)],
)
def test_reads_the_project_concurrency(
    tmp_path: Path, read_path: mock.MagicMock, text: str, concurrency: int
) -> None:
    assert read_config(write(tmp_path, text)).concurrency == concurrency


def test_rejects_a_bad_concurrency(tmp_path: Path, read_path: mock.MagicMock) -> None:
    path = write(tmp_path, "[experiments]\nconcurrency = 0\n")

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == (
        f"{path}: [experiments] concurrency must be a positive integer"
    )


@pytest.mark.parametrize(
    ("text", "retries"),
    [("", 2), ("[experiments]\nretries = 0\n", 0), ("[experiments]\nretries = 5\n", 5)],
)
def test_reads_the_project_retries(
    tmp_path: Path, read_path: mock.MagicMock, text: str, retries: int
) -> None:
    assert read_config(write(tmp_path, text)).retries == retries


@pytest.mark.parametrize("value", ["-1", '"2"'])
def test_rejects_bad_retries(
    tmp_path: Path, read_path: mock.MagicMock, value: str
) -> None:
    path = write(tmp_path, f"[experiments]\nretries = {value}\n")

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == f"{path}: [experiments] retries must be 0 or more"


def test_rejects_unknown_tables(tmp_path: Path, read_path: mock.MagicMock) -> None:
    path = write(tmp_path, "zz = 1\n[data]\n")

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == f"{path}: unknown tables data, zz"


def test_rejects_invalid_toml(tmp_path: Path, read_path: mock.MagicMock) -> None:
    path = write(tmp_path, "[runs]\npath = \n")

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value).startswith(f"{path}: ")


def test_a_project_without_experiment_toml_holds_many(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    assert read_config(write(tmp_path, "")).experiment is None


def test_experiment_toml_beside_the_config_makes_one_experiment(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    project = tmp_path / "surprisals"
    project.mkdir()
    (project / "experiment.toml").write_text('command = "x"\n', encoding="utf-8")
    path = write(project, "")

    config = read_config(path)

    assert config.experiment == "surprisals"
    assert read_path.call_args_list[0] == mock.call(
        path, "experiments", {}, single=True
    )


def test_reads_the_experiment_defaults(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    path = write(
        tmp_path,
        '[experiment]\ncommand = "go"\nretries = 3\n[experiment.params]\nm = [1]\n',
    )

    assert read_config(path).defaults == {
        "command": "go",
        "retries": 3,
        "params": {"m": [1]},
    }


def test_has_no_defaults_without_an_experiment_table(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    assert read_config(write(tmp_path, "")).defaults == {}


def test_an_experiment_table_alone_makes_one_experiment(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    project = tmp_path / "study"
    project.mkdir()

    config = read_config(write(project, '[experiment]\ncommand = "go"\n'))

    assert config.experiment == "study"


def test_an_experiments_path_keeps_many_experiments_with_defaults(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    path = write(
        tmp_path,
        '[experiments]\npath = "{experiment}"\n[experiment]\ncommand = "go"\n',
    )

    config = read_config(path)

    assert (config.experiment, config.defaults) == (None, {"command": "go"})


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("experiment = 1\n", "experiment must be a table, like [experiment]"),
        ("[experiment]\nzz = 1\npath = 2\n", "unknown keys in [experiment]: path, zz"),
    ],
)
def test_rejects_a_bad_experiment_table(
    tmp_path: Path, read_path: mock.MagicMock, text: str, message: str
) -> None:
    path = write(tmp_path, text)

    with pytest.raises(ValueError) as error:
        read_config(path)

    assert str(error.value) == f"{path}: {message}"


def test_a_non_table_experiments_still_fails_in_read_path(
    tmp_path: Path, read_path: mock.MagicMock
) -> None:
    read_path.side_effect = ValueError("bad")

    with pytest.raises(ValueError, match="bad"):
        read_config(write(tmp_path, 'experiments = 1\n[experiment]\ncommand = "go"\n'))
