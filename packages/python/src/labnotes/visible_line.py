def visible_line(line: str) -> str:
    """What a terminal leaves on screen: the last non-empty `\\r` overwrite."""
    return line.rstrip("\r").rsplit("\r", 1)[-1]
