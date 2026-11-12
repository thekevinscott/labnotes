from pathlib import Path

from labnotes.latest_log import latest_log


def invocation_logs(folder: Path, stream: str) -> list[tuple[str | None, Path]]:
    return [(None, latest_log(folder, stream))]
