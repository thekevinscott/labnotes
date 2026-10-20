from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.runner.signal_tree import signal_tree


class Gone(Exception):
    pass


@pytest.fixture
def psutil() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.runner.signal_tree.psutil") as psutil:
        psutil.NoSuchProcess = Gone
        yield psutil


def test_signals_the_process_and_everything_under_it(psutil: mock.MagicMock) -> None:
    child, grandchild = mock.Mock(), mock.Mock()
    root = mock.Mock(children=mock.Mock(return_value=[child, grandchild]))
    psutil.Process.return_value = root
    tree: set[object] = set()

    signal_tree(42, 15, tree)  # type: ignore[arg-type]

    psutil.Process.assert_called_once_with(42)
    root.children.assert_called_once_with(recursive=True)
    assert tree == {root, child, grandchild}
    for member in tree:
        member.send_signal.assert_called_once_with(15)  # type: ignore[attr-defined]


def test_still_signals_what_was_left_behind_once_the_shell_is_gone(
    psutil: mock.MagicMock,
) -> None:
    orphan = mock.Mock()
    tree = {orphan}
    psutil.Process.side_effect = Gone()

    signal_tree(42, 9, tree)  # type: ignore[arg-type]

    assert tree == {orphan}
    orphan.send_signal.assert_called_once_with(9)


def test_skips_a_process_that_exits_meanwhile(psutil: mock.MagicMock) -> None:
    gone = mock.Mock(send_signal=mock.Mock(side_effect=Gone()))
    alive = mock.Mock()
    psutil.Process.return_value = mock.Mock(
        children=mock.Mock(return_value=[gone, alive])
    )
    tree: set[object] = set()

    signal_tree(42, 15, tree)  # type: ignore[arg-type]

    alive.send_signal.assert_called_once_with(15)
