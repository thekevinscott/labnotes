import subprocess
import sys
import time
from collections.abc import Iterator

import psutil
import pytest

from labnotes.utils.tree_rss import tree_rss

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


def test_sums_the_resident_memory_of_a_real_tree(parent: psutil.Process) -> None:
    [child] = parent.children()
    own = parent.memory_info().rss

    total = tree_rss(parent.pid, parent.create_time())

    assert total is not None
    assert total >= own + child.memory_info().rss // 2


def test_has_nothing_for_a_process_that_exited() -> None:
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()

    assert tree_rss(process.pid, 0.0) is None
