from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.utils.tree_rss import tree_rss


class Gone(Exception):
    pass


class Denied(Exception):
    pass


@pytest.fixture
def psutil() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.utils.tree_rss.psutil") as psutil:
        psutil.NoSuchProcess = Gone
        psutil.AccessDenied = Denied
        yield psutil


def using(rss: int, created: float = 50.0) -> mock.Mock:
    found = mock.Mock()
    found.memory_info.return_value.rss = rss
    found.create_time.return_value = created
    return found


def test_sums_the_resident_memory_of_the_whole_tree(psutil: mock.MagicMock) -> None:
    root = using(100)
    root.children.return_value = [using(20), using(3)]
    psutil.Process.return_value = root

    assert tree_rss(7, 50.0) == 123
    psutil.Process.assert_called_once_with(7)
    root.children.assert_called_once_with(recursive=True)


def test_has_nothing_for_a_process_that_is_gone(psutil: mock.MagicMock) -> None:
    psutil.Process.side_effect = Gone()

    assert tree_rss(7, 50.0) is None


@pytest.mark.parametrize("created", [51.0, 49.0])
def test_has_nothing_for_a_pid_reused_by_another_process(
    psutil: mock.MagicMock, created: float
) -> None:
    psutil.Process.return_value = using(100, created=created)

    assert tree_rss(7, 50.0) is None


@pytest.mark.parametrize("created", [0.004, 0.01])
def test_allows_for_rounding_in_the_recorded_start(
    psutil: mock.MagicMock, created: float
) -> None:
    psutil.Process.return_value = using(100, created=created)
    psutil.Process.return_value.children.return_value = []

    assert tree_rss(7, 0.0) == 100


def test_has_nothing_when_the_start_cannot_be_read(psutil: mock.MagicMock) -> None:
    psutil.Process.return_value.create_time.side_effect = Denied()

    assert tree_rss(7, 50.0) is None


def test_skips_a_child_that_vanishes_mid_walk(psutil: mock.MagicMock) -> None:
    root = using(100)
    gone = mock.Mock()
    gone.memory_info.side_effect = Gone()
    hidden = mock.Mock()
    hidden.memory_info.side_effect = Denied()
    root.children.return_value = [gone, hidden, using(20)]
    psutil.Process.return_value = root

    assert tree_rss(1, 50.0) == 120


def test_has_nothing_when_the_root_dies_while_listing_children(
    psutil: mock.MagicMock,
) -> None:
    psutil.Process.return_value = using(100)
    psutil.Process.return_value.children.side_effect = Gone()

    assert tree_rss(1, 50.0) is None


def test_keeps_the_roots_memory_when_its_children_are_hidden(
    psutil: mock.MagicMock,
) -> None:
    psutil.Process.return_value = using(100)
    psutil.Process.return_value.children.side_effect = Denied()

    assert tree_rss(1, 50.0) == 100


def test_has_nothing_when_no_memory_can_be_read(psutil: mock.MagicMock) -> None:
    root = using(100)
    root.memory_info.side_effect = Denied()
    root.children.return_value = []
    psutil.Process.return_value = root

    assert tree_rss(1, 50.0) is None
