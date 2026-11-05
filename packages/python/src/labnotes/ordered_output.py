import json
from collections.abc import Iterable
from pathlib import Path

from labnotes.latest_log import latest_log
from labnotes.output_files import output_files

STREAMS = ("stdout", "stderr")


class OrderedOutput:
    def __init__(self) -> None:
        self.offsets = dict.fromkeys(STREAMS, 0)
        self.paths: dict[str, Path] = {}
        self.index: Path | None = None
        self.index_read = 0

    def read(
        self, folder: Path, streams: Iterable[str] = STREAMS
    ) -> list[tuple[str, bytes]]:
        files = output_files(folder)
        if files is None:
            return self.read_each(folder, streams)
        if files["output"] != self.index:
            self.index = files["output"]
            self.index_read = 0
            self.offsets = dict.fromkeys(STREAMS, 0)
            self.paths = {stream: files[stream] for stream in STREAMS}
        return self.read_indexed()

    def read_indexed(self) -> list[tuple[str, bytes]]:
        assert self.index is not None
        if not self.index.exists():
            return []
        with self.index.open("rb") as index:
            index.seek(self.index_read)
            data = index.read()
        whole = data[: data.rfind(b"\n") + 1]
        self.index_read += len(whole)
        # Consecutive entries for one stream make one read.
        runs: list[tuple[str, int]] = []
        for line in whole.splitlines():
            try:
                entry = json.loads(line)
                stream, end = entry["stream"], entry["end"]
            except (ValueError, TypeError, KeyError):
                continue
            if stream not in STREAMS or not isinstance(end, int):
                continue
            if runs and runs[-1][0] == stream:
                runs[-1] = (stream, end)
            else:
                runs.append((stream, end))
        chunks: list[tuple[str, bytes]] = []
        for stream, end in runs:
            start = self.offsets[stream]
            if end <= start:
                continue
            with self.paths[stream].open("rb") as log:
                log.seek(start)
                data = log.read(end - start)
            self.offsets[stream] = start + len(data)
            chunks.append((stream, data))
        return chunks

    def read_each(
        self, folder: Path, streams: Iterable[str]
    ) -> list[tuple[str, bytes]]:
        chunks: list[tuple[str, bytes]] = []
        for stream in streams:
            path = latest_log(folder, stream)
            if not path.exists():
                continue
            if self.paths.setdefault(stream, path) != path:
                self.paths[stream] = path
                self.offsets[stream] = 0
            with path.open("rb") as log:
                log.seek(self.offsets[stream])
                data = log.read()
            self.offsets[stream] += len(data)
            chunks.append((stream, data))
        return chunks
