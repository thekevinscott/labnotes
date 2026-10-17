from pathlib import Path

import click
import pytest

from labnotes.load_config import load_config


def context_for(path: Path) -> click.Context:
    ctx = click.Context(click.Command("labnotes"))
    ctx.obj = path
    return ctx


def test_returns_none_without_a_config(tmp_path: Path) -> None:
    assert load_config(context_for(tmp_path / ".labnotes.toml")) is None


def test_reads_the_config(tmp_path: Path) -> None:
    path = tmp_path / ".labnotes.toml"
    path.write_text("", encoding="utf-8")

    config = load_config(context_for(path))

    assert config is not None
    assert config.path == path


def test_reports_a_broken_config_as_a_click_error(tmp_path: Path) -> None:
    path = tmp_path / ".labnotes.toml"
    path.write_text("zz = 1\n", encoding="utf-8")

    with pytest.raises(click.ClickException) as error:
        load_config(context_for(path))

    assert error.value.message == f"{path}: unknown keys zz"
