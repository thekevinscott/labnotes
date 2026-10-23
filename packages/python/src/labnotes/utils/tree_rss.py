import contextlib

import psutil

# run.json round-trips create_time through JSON, and psutil derives it from
# boot time, so allow a little slack when matching.
SAME_START_SECONDS = 0.01


def tree_rss(pid: int, created: float) -> int | None:
    try:
        root = psutil.Process(pid)
        if abs(root.create_time() - created) > SAME_START_SECONDS:
            return None
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
    try:
        tree = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied:
        tree = [root]
    sizes = []
    for process in tree:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            sizes.append(process.memory_info().rss)
    return sum(sizes) if sizes else None
