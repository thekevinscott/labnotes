import signal


def exit_signal(exit_code: int | None) -> int | None:
    if exit_code is None:
        return None
    if exit_code < 0:
        return -exit_code
    # A shell reports a child killed by signal N as exit 128 + N.
    number = exit_code - 128
    return number if 0 < number < signal.NSIG else None
