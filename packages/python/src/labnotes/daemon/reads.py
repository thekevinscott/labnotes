"""Serve experiment state from the daemon's one DirSQL as server-sent events."""

import codecs
import hashlib
import json
import mimetypes
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Collection
from pathlib import Path
from typing import Any

from dirsql import DirSQL
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from labnotes.daemon.sse import sse
from labnotes.tables.iso_time import iso_time

TAIL_BYTES = 64 * 1024
SNIFF_BYTES = 8192
STAMP = re.compile(r"^\d{8}-\d{6}-")
RUNS = """
SELECT
  r.id,
  r.created AS started,
  CASE
    WHEN r.ended IS NULL AND r.exit_code IS NULL AND r.error IS NULL THEN 'running'
    WHEN r.run ->> 'ended_by' IS NOT NULL THEN r.run ->> 'ended_by'
    WHEN r.exit_code = 0 AND r.error IS NULL THEN 'succeeded'
    ELSE 'failed'
  END AS status,
  (SELECT m.rss FROM memory AS m WHERE m.run = r.id ORDER BY m.line DESC LIMIT 1)
    AS memory,
  (SELECT coalesce(sum(f.size), 0) FROM run_files AS f
    WHERE substr(f.path, 1, length(r.folder) + 1) = r.folder || '/') AS size
FROM runs AS r
ORDER BY r.created, r.id
"""
FILES = """
SELECT substr(path, length(:folder) + 2) AS name, size, mtime_ns FROM run_files
WHERE substr(path, 1, length(:folder) + 1) = :folder || '/'
ORDER BY name
"""
MISSING = {"ok": False, "error": "Not found"}
Rows = Callable[[], Awaitable[list[dict[str, Any]]]]


class Reads:
    """Answer each read route from the tables, then follow their changes."""

    def __init__(self, root: Path, tables: DirSQL) -> None:
        self.root = root
        self.tables = tables
        self.routes = [
            Route("/runs", self.runs),
            Route("/runs/{run:path}/files/{file:path}", self.file),
            Route("/runs/{run:path}/files", self.files),
        ]

    async def runs(self, request: Request) -> Response:
        async def rows() -> list[dict[str, Any]]:
            found = await self.tables.query(RUNS)
            return [
                {**row, "name": STAMP.sub("", row["id"].rsplit("/", 1)[-1])}
                for row in found
            ]

        return self.follow(request, rows, "id", "run", {"runs", "memory", "run_files"})

    async def files(self, request: Request) -> Response:
        folder = await self.folder(request.path_params["run"])
        if folder is None:
            return JSONResponse(MISSING, 404)

        async def rows() -> list[dict[str, Any]]:
            found = await self.tables.query(FILES, {"folder": folder})
            return [
                {
                    "name": row["name"],
                    "size": row["size"],
                    "mtime": iso_time(row["mtime_ns"] / 1e9),
                }
                for row in found
            ]

        return self.follow(request, rows, "name", "file", {"run_files"})

    async def file(self, request: Request) -> Response:
        name = request.path_params["file"]
        folder = await self.folder(request.path_params["run"])
        relative = f"{folder}/{name}"
        if folder is None or not await self.tables.query(
            "SELECT 1 FROM run_files WHERE path = ?", [relative]
        ):
            return JSONResponse(MISSING, 404)
        last = request.headers.get("last-event-id")
        return StreamingResponse(
            self.follow_file(relative, name, last), media_type="text/event-stream"
        )

    async def folder(self, run: str) -> str | None:
        found = await self.tables.query("SELECT folder FROM runs WHERE id = ?", [run])
        return found[0]["folder"] if found else None

    def follow(
        self, request: Request, rows: Rows, key: str, kind: str, names: Collection[str]
    ) -> Response:
        """Send current state unless the client already holds it, then each change."""
        last = request.headers.get("last-event-id")

        async def stream() -> AsyncIterator[str]:
            await self.tables.ready()
            changes = self.tables.watch()
            shown = {row[key]: row for row in await rows()}
            if last != self.state_id(shown):
                yield sse(list(shown.values()), "state", self.state_id(shown))
            async for change in changes:
                if change.table not in names:
                    continue
                latest = {row[key]: row for row in await rows()}
                for gone in [name for name in shown if name not in latest]:
                    del shown[gone]
                    yield sse({key: gone}, "remove", self.state_id(shown))
                for name, row in latest.items():
                    if shown.get(name) != row:
                        shown[name] = row
                        yield sse(row, kind, self.state_id(shown))

        return StreamingResponse(stream(), media_type="text/event-stream")

    async def follow_file(
        self, relative: str, name: str, last: str | None
    ) -> AsyncIterator[str]:
        """Send a text file's tail then its appended text; a binary file's size and type."""
        await self.tables.ready()
        changes = self.tables.watch()
        path = self.root / relative
        size = path.stat().st_size
        with path.open("rb") as handle:
            binary = self.binary(handle.read(SNIFF_BYTES))
        kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        fed = size
        if binary:
            if last != str(size):
                yield sse(
                    {"name": name, "size": size, "type": kind}, "state", str(size)
                )
        elif last is not None and last.isdigit() and int(last) <= size:
            fed = int(last)
            text = decoder.decode(self.read(path, fed, size))
            fed = size
            if text:
                yield sse({"text": text}, "append", self.offset(fed, decoder))
        else:
            text = self.tail(path, size, decoder)
            yield sse(
                {"name": name, "size": size, "text": text},
                "state",
                self.offset(fed, decoder),
            )
        async for change in changes:
            if change.table != "run_files" or relative not in (
                (change.row or {}).get("path"),
                (change.old_row or {}).get("path"),
            ):
                continue
            try:
                grown = path.stat().st_size
            except FileNotFoundError:
                yield sse({"name": name}, "remove", self.offset(fed, decoder))
                return
            if binary:
                if grown != size:
                    size = grown
                    yield sse(
                        {"name": name, "size": size, "type": kind}, "state", str(size)
                    )
            elif grown < fed:
                decoder.reset()
                fed = grown
                text = self.tail(path, grown, decoder)
                yield sse(
                    {"name": name, "size": grown, "text": text},
                    "state",
                    self.offset(fed, decoder),
                )
            elif grown > fed:
                text = decoder.decode(self.read(path, fed, grown))
                fed = grown
                if text:
                    yield sse({"text": text}, "append", self.offset(fed, decoder))

    def tail(self, path: Path, size: int, decoder: codecs.IncrementalDecoder) -> str:
        start = max(0, size - TAIL_BYTES)
        chunk = self.read(path, start, size)
        if start:
            chunk = chunk[chunk.find(b"\n") + 1 :]
        return decoder.decode(chunk)

    @staticmethod
    def read(path: Path, start: int, end: int) -> bytes:
        with path.open("rb") as handle:
            handle.seek(start)
            return handle.read(end - start)

    @staticmethod
    def binary(head: bytes) -> bool:
        if b"\0" in head:
            return True
        try:
            codecs.getincrementaldecoder("utf-8")().decode(head)
        except UnicodeDecodeError:
            return True
        return False

    @staticmethod
    def offset(fed: int, decoder: codecs.IncrementalDecoder) -> str:
        """The byte offset a resuming client continues from: held-back bytes excluded."""
        return str(fed - len(decoder.getstate()[0]))

    @staticmethod
    def state_id(state: dict[str, Any]) -> str:
        encoded = json.dumps(state, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]
