import contextlib

import psutil


def tree_rss(pid: int) -> int | None:
    try:
        root = psutil.Process(pid)
        tree = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return None
    total = 0
    for process in tree:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            total += process.memory_info().rss
    return total
