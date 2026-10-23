import subprocess
import sys
import time
from collections.abc import Iterator
from unittest import mock

import psutil
import pytest

from labnotes.tree_rss import tree_rss

# A parent holding a child, so the tree has two processes.
NESTED = (
    "import subprocess, sys, time;"
    "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']);"
    "time.sleep(30)"
)


@pytest.fixture
def parent() -> Iterator[psutil.Process]:
    process = subprocess.Popen([sys.executable, "-c", NESTED])
    root = psutil.Process(process.pid)
    try:
        for _ in range(100):
            if root.children():
                break
            time.sleep(0.05)
        yield root
    finally:
        for child in root.children(recursive=True):
            child.kill()
        process.kill()
        process.wait()


def test_sums_the_resident_memory_of_the_whole_tree(parent: psutil.Process) -> None:
    [child] = parent.children()
    own = parent.memory_info().rss

    total = tree_rss(parent.pid)

    assert total is not None
    assert total > own
    assert total >= own + child.memory_info().rss // 2


def test_has_nothing_for_a_process_that_is_gone() -> None:
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()

    assert tree_rss(process.pid) is None


def test_skips_a_child_that_vanishes_mid_walk() -> None:
    root = mock.Mock()
    root.memory_info.return_value.rss = 100
    gone = mock.Mock()
    gone.memory_info.side_effect = psutil.NoSuchProcess(2)
    hidden = mock.Mock()
    hidden.memory_info.side_effect = psutil.AccessDenied(3)
    alive = mock.Mock()
    alive.memory_info.return_value.rss = 20
    root.children.return_value = [gone, hidden, alive]

    with mock.patch("labnotes.tree_rss.psutil.Process", return_value=root):
        assert tree_rss(1) == 120
    root.children.assert_called_once_with(recursive=True)


def test_has_nothing_when_the_root_dies_while_listing_children() -> None:
    root = mock.Mock()
    root.children.side_effect = psutil.NoSuchProcess(1)

    with mock.patch("labnotes.tree_rss.psutil.Process", return_value=root):
        assert tree_rss(1) is None
