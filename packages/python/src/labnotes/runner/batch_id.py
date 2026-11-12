"""Name one invocation for daemon clients and its hook logs."""

import os
import time
from uuid import uuid4


def batch_id() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    return f"{stamp}-{os.getpid()}-{uuid4().hex[:8]}"
