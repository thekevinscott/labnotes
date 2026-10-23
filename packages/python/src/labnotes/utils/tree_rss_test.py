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


def using(rss: int) -> mock.Mock:
    found = mock.Mock()
    found.memory_info.return_value.rss = rss
    return found


def test_sums_the_resident_memory_of_the_whole_tree(psutil: mock.MagicMock) -> None:
    root = using(100)
    root.children.return_value = [using(20), using(3)]
    psutil.Process.return_value = root

    assert tree_rss(7) == 123
    psutil.Process.assert_called_once_with(7)
    root.children.assert_called_once_with(recursive=True)


def test_has_nothing_for_a_process_that_is_gone(psutil: mock.MagicMock) -> None:
    psutil.Process.side_effect = Gone()

    assert tree_rss(7) is None


def test_skips_a_child_that_vanishes_mid_walk(psutil: mock.MagicMock) -> None:
    root = using(100)
    gone = mock.Mock()
    gone.memory_info.side_effect = Gone()
    hidden = mock.Mock()
    hidden.memory_info.side_effect = Denied()
    root.children.return_value = [gone, hidden, using(20)]
    psutil.Process.return_value = root

    assert tree_rss(1) == 120


def test_has_nothing_when_the_root_dies_while_listing_children(
    psutil: mock.MagicMock,
) -> None:
    psutil.Process.return_value.children.side_effect = Gone()

    assert tree_rss(1) is None
