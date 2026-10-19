import hashlib
import time


def new_invocation_id() -> str:
    return hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]
