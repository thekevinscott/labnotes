import psutil

from labnotes.utils.tree_usage import SAME_START_SECONDS


def process_alive(pid: int, created: float | None) -> bool:
    try:
        started = psutil.Process(pid).create_time()
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
    return created is None or abs(started - created) <= SAME_START_SECONDS
