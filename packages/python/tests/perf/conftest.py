import faulthandler
from collections.abc import Iterator

import pytest

TIMEOUT_SECONDS = 120


@pytest.fixture(autouse=True)
def hard_timeout() -> Iterator[None]:
    # A frozen event loop never reaches an assertion. The watchdog thread
    # still fires, dumps every stack, and exits.
    faulthandler.dump_traceback_later(TIMEOUT_SECONDS, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
