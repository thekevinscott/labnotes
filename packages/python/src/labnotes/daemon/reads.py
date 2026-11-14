"""Serve experiment state from the daemon's one DirSQL as server-sent events."""

import codecs
import hashlib
import json
import mimetypes
import os
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
MARK_BYTES = 64
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
            Route("/runs/{path:path}", self.run_path),
        ]

    async def runs(self, request: Request) -> Response:
        async def rows() -> list[dict[str, Any]]:
            found = await self.tables.query(RUNS)
            return [
                {**row, "name": STAMP.sub("", row["id"].rsplit("/", 1)[-1])}
                for row in found
            ]

        return self.follow(request, rows, "id", "run", {"runs", "memory", "run_files"})

    async def run_path(self, request: Request) -> Response:
        """Split the path at the first `files` segment that follows a known run."""
        parts = request.path_params["path"].split("/")
        for at in range(1, len(parts)):
            if parts[at] != "files":
                continue
            folder = await self.folder("/".join(parts[:at]))
            if folder is None:
                continue
            name = "/".join(parts[at + 1 :])
            if not name:
                return self.files(request, folder)
            return await self.file(request, folder, name)
        return JSONResponse(MISSING, 404)

    def files(self, request: Request, folder: str) -> Response:
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

    async def file(self, request: Request, folder: str, name: str) -> Response:
        relative = f"{folder}/{name}"
        if not await self.tables.query(
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
        stat = path.stat()
        with path.open("rb") as handle:
            binary = self.binary(handle.read(SNIFF_BYTES))

        async def touched() -> AsyncIterator[os.stat_result | None]:
            async for change in changes:
                if self.touches(change, relative):
                    try:
                        yield path.stat()
                    except FileNotFoundError:
                        yield None

        if binary:
            kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
            seen = (stat.st_size, stat.st_mtime_ns)
            if last != str(stat.st_size):
                yield sse(
                    {"name": name, "size": stat.st_size, "type": kind},
                    "state",
                    str(stat.st_size),
                )
            async for found in touched():
                if found is None:
                    yield sse({"name": name}, "remove", str(seen[0]))
                    return
                if (found.st_size, found.st_mtime_ns) != seen:
                    seen = (found.st_size, found.st_mtime_ns)
                    yield sse(
                        {"name": name, "size": found.st_size, "type": kind},
                        "state",
                        str(found.st_size),
                    )
            return
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        inode = stat.st_ino
        start = int(last) if last is not None and last.isdigit() else -1
        resumed = 0 <= start <= stat.st_size
        if resumed:
            fed = start
        else:
            fed = stat.st_size
            text = self.tail(path, fed, decoder)
            yield sse(
                {"name": name, "size": fed, "text": text},
                "state",
                self.offset(fed, decoder),
            )
        mark = self.read(path, max(0, fed - MARK_BYTES), fed)

        async def updates() -> AsyncIterator[os.stat_result | None]:
            if resumed:
                yield stat
            async for found in touched():
                yield found

        async for found in updates():
            if found is None:
                yield sse({"name": name}, "remove", self.offset(fed, decoder))
                return
            if (
                found.st_ino != inode
                or found.st_size < fed
                or self.read(path, max(0, fed - MARK_BYTES), fed) != mark
            ):
                decoder.reset()
                inode, fed = found.st_ino, found.st_size
                text = self.tail(path, fed, decoder)
                yield sse(
                    {"name": name, "size": fed, "text": text},
                    "state",
                    self.offset(fed, decoder),
                )
            elif found.st_size > fed:
                text = decoder.decode(self.read(path, fed, found.st_size))
                fed = found.st_size
                if text:
                    yield sse({"text": text}, "append", self.offset(fed, decoder))
            mark = self.read(path, max(0, fed - MARK_BYTES), fed)

    @staticmethod
    def touches(change: Any, relative: str) -> bool:
        return change.table == "run_files" and relative in (
            (change.row or {}).get("path"),
            (change.old_row or {}).get("path"),
        )

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
