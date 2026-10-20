import codecs
import json
from collections.abc import AsyncIterator, Iterable, Iterator
from pathlib import Path

from dirsql import DirSQL

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
    offsets = dict.fromkeys(STREAMS, 0)
    decoders = {
        stream: codecs.getincrementaldecoder("utf-8")("replace") for stream in STREAMS
    }
    last: str | None = None
    mid_line = False

    def read(streams: Iterable[str]) -> Iterator[str]:
        nonlocal last, mid_line
        for stream in streams:
            path = folder / f"{stream}.log"
            if not path.exists():
                continue
            with path.open("rb") as log:
                log.seek(offsets[stream])
                data = log.read()
            offsets[stream] += len(data)
            text = decoders[stream].decode(data)
            if not text:
                continue
            if mid_line and stream != last:
                text = "\n" + text
            last, mid_line = stream, not text.endswith("\n")
            yield f"data: {json.dumps({'stream': stream, 'text': text})}\n\n"

    for message in read(STREAMS):
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
            elif (
                event.table == "runs"
                and row["id"] == run_id
                and row["ended"] is not None
            ):
                exit_code = row["exit_code"]
                break
        for message in read(STREAMS):
            yield message
    yield f"event: end\ndata: {json.dumps(exit_code)}\n\n"
