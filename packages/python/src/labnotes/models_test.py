import typing
from collections.abc import Callable
from pathlib import Path

from labnotes.models import Controls, LabnotesConfig, RunView


def test_a_run_view_starts_unsorted_and_unfiltered() -> None:
    view = RunView()

    assert (view.sort, view.descending, view.status) == (None, False, None)
    assert (view.filters, view.picked) == ({}, {})


def test_run_views_do_not_share_their_picks() -> None:
    view = RunView()
    view.picked["model"] = {"a": '"a"'}

    assert RunView().picked == {}


def test_move_takes_a_run_and_its_new_place() -> None:
    hint = typing.get_type_hints(Controls)["move"]

    assert hint == Callable[[str, int], None]


def test_a_config_holds_many_experiments_by_default() -> None:
    config = LabnotesConfig(Path("/p/.labnotes.toml"), Path("/p"), "e", "f", "r")

    assert config.experiment is None
