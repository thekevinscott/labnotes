import contextlib

import psutil


def signal_tree(pid: int, signal_number: int, tree: set[psutil.Process]) -> None:
    with contextlib.suppress(psutil.NoSuchProcess):
        root = psutil.Process(pid)
        tree.update([root, *root.children(recursive=True)])
    for process in tree:
        with contextlib.suppress(psutil.NoSuchProcess):
            process.send_signal(signal_number)
