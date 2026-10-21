from pathlib import Path

STREAMS = ("stdout", "stderr")
Key = tuple[str, str]


class RunLogs:
    """The latest line each running run wrote, read from its logs by byte offset."""

    def __init__(self) -> None:
        self.folders: dict[Key, Path] = {}
        self.offsets: dict[tuple[Key, str], int] = {}
        self.partial: dict[tuple[Key, str], bytes] = {}

    def add(self, experiment: str, run: str, folder: Path) -> None:
        self.folders[experiment, run] = folder

    def drop(self, experiment: str, run: str) -> None:
        self.folders.pop((experiment, run), None)

    def latest(self) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for key, folder in self.folders.items():
            for stream in STREAMS:
                line = self.read(key, stream, folder / f"{stream}.log")
                if line is not None:
                    experiment, run = key
                    found.append(
                        {
                            "event": "output",
                            "experiment": experiment,
                            "run": run,
                            "stream": stream,
                            "line": line,
                        }
                    )
        return found

    def read(self, key: Key, stream: str, path: Path) -> str | None:
        try:
            with path.open("rb") as log:
                log.seek(self.offsets.get((key, stream), 0))
                data = log.read()
        except FileNotFoundError:
            return None
        self.offsets[key, stream] = self.offsets.get((key, stream), 0) + len(data)
        *complete, rest = (self.partial.get((key, stream), b"") + data).split(b"\n")
        self.partial[key, stream] = rest
        shown = [
            text
            for line in complete
            if (text := line.rsplit(b"\r")[-1].decode(errors="replace").strip())
        ]
        return shown[-1] if shown else None
