from collections.abc import Callable

from haikunator import Haikunator


def new_run_id(taken: Callable[[str], bool]) -> str:
    name = Haikunator().haikunate(token_length=0)
    candidate, suffix = name, 2
    while taken(candidate):
        candidate, suffix = f"{name}-{suffix}", suffix + 1
    return candidate
