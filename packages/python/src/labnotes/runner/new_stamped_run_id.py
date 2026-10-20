from collections.abc import Callable
from datetime import UTC, datetime

from labnotes.runner.new_run_id import new_run_id


def new_stamped_run_id(taken: Callable[[str], bool]) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-" + new_run_id(lambda name: taken(f"{stamp}-{name}"))
