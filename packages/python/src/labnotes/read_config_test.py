from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.read_config import read_config


@pytest.fixture
def read_path() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.read_config.read_path", side_effect=lambda _, table, __: table
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
        mock.call(path, "experiments", {}),
        mock.call(path, "files", {}),
        mock.call(path, "runs", {"path": "x"}),
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
        ('[experiments]\nmode = "fill"\n', "fill"),
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

    assert str(error.value) == f"{path}: [experiments] mode must be fill or adhoc"


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
