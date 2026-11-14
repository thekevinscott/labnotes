import re

OSC_BEL = re.compile(r"\x1b\][^\x07\x1b]*\x07")


def terminal_line(raw: str) -> str:
    """Return the last non-empty overwrite of a line, as a terminal shows it.

    Overwrites replace the whole line rather than overlaying columns, and
    color set before the last overwrite is dropped.
    """
    segments = [segment for segment in OSC_BEL.sub("", raw).split("\r") if segment]
    return segments[-1] if segments else ""
