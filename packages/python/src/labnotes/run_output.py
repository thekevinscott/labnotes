import json
from collections.abc import AsyncIterator, Iterable, Iterator
from pathlib import Path

from dirsql import DirSQL

from labnotes.latest_log import latest_log
from labnotes.line_index import LineIndex
from labnotes.load_run import load_run
from labnotes.tables.read_log import STREAMS


async def run_output(
    tables: DirSQL, root: Path, experiment: str, run_id: str
) -> AsyncIterator[str]:
    # Watch before reading, so nothing written in between is missed.
    events = tables.watch()
    run = await load_run(tables, experiment, run_id)
    if run is None:
        return
    folder = root / str(run["folder"])
    indexes: dict[str, LineIndex] = {}

    def read(streams: Iterable[str]) -> Iterator[str]:
        for stream in streams:
            path = latest_log(folder, stream)
            if not path.exists():
                continue
            old = indexes.get(stream)
            kept = (
                old is not None
                and old.path == path
                and path.stat().st_size >= old.scanned
            )
            index = indexes[stream] = (
                old if old is not None and kept else LineIndex(path)
            )
            if not index.extend() and kept:
                continue
            message = {
                "stream": stream,
                "file": path.name,
                "fresh": not kept,
                "rows": index.rows,
                "lines": index.lines,
            }
            yield f"data: {json.dumps(message)}\n\n"

    blocks_read = 0

    def read_blocks() -> Iterator[str]:
        nonlocal blocks_read
        path = folder / "log.jsonl"
        if not path.exists():
            return
        with path.open("rb") as log:
            log.seek(blocks_read)
            data = log.read()
        whole = data[: data.rfind(b"\n") + 1]
        blocks_read += len(whole)
        for line in whole.splitlines():
            try:
                record = json.loads(line.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if isinstance(record, dict):
                yield f"event: block\ndata: {json.dumps(record)}\n\n"

    for message in read(STREAMS):
        yield message
    for message in read_blocks():
        yield message
    exit_code = run["exit_code"]
    if run["ended"] is None:
        async for event in events:
            row = event.row
            if row is None or row["experiment"] != experiment:
                continue
            if event.table == "logs" and row["run"] == run_id:
                for message in read([row["stream"]]):
                    yield message
            elif event.table == "blocks" and row["run"] == run_id:
                for message in read_blocks():
                    yield message
            elif (
                event.table == "runs"
                and row["id"] == run_id
                and row["ended"] is not None
            ):
                exit_code = row["exit_code"]
                break
        for message in read(STREAMS):
            yield message
        for message in read_blocks():
            yield message
    yield f"event: end\ndata: {json.dumps(exit_code)}\n\n"
