from pathlib import Path

from posix_tools import tail


async def last_stderr(folder: Path) -> str | None:
    try:
        lines = await tail(folder / "stderr.log", n=50)
    except FileNotFoundError:
        return None
    for line in reversed(lines):
        shown = line.rstrip(b"\r\n").rsplit(b"\r")[-1]
        if text := shown.decode(errors="replace").strip():
            return text
    return None
