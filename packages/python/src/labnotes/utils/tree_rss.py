from labnotes.utils.tree_usage import tree_usage


def tree_rss(pid: int, created: float) -> int | None:
    usage = tree_usage(pid, created)
    return None if usage is None else usage[0]
