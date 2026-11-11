import signal


def exit_signal(exit_code: int | None) -> int | None:
    if exit_code is None:
        return None
    if exit_code < 0:
        return -exit_code
    # A shell reports a child killed by signal N as exit 128 + N.
    high, number = divmod(exit_code, 128)
    return number if high == 1 and number in range(1, signal.NSIG) else None
