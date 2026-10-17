from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.load_config import load_config


class FakeClickException(Exception):
    pass


@pytest.fixture
def read_config() -> Iterator[mock.MagicMock]:
    with (
        mock.patch("labnotes.load_config.read_config") as read_config,
        mock.patch("labnotes.load_config.click.ClickException", FakeClickException),
    ):
        yield read_config


def context_for(path: Path) -> mock.MagicMock:
    ctx = mock.MagicMock()
    ctx.find_root.return_value.obj = path
    return ctx


def test_returns_none_without_a_config(
    tmp_path: Path, read_config: mock.MagicMock
) -> None:
    assert load_config(context_for(tmp_path / ".labnotes.toml")) is None
    read_config.assert_not_called()


def test_reads_the_config(tmp_path: Path, read_config: mock.MagicMock) -> None:
    path = tmp_path / ".labnotes.toml"
    path.write_text("", encoding="utf-8")

    assert load_config(context_for(path)) == read_config.return_value
    read_config.assert_called_once_with(path)


def test_reports_a_broken_config_as_a_click_error(
    tmp_path: Path, read_config: mock.MagicMock
) -> None:
    path = tmp_path / ".labnotes.toml"
    path.write_text("", encoding="utf-8")
    read_config.side_effect = ValueError("broken")

    with pytest.raises(FakeClickException) as error:
        load_config(context_for(path))

    assert str(error.value) == "broken"
