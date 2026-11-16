"""Serve what the run TUI's views show, from the daemon's one DirSQL."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from dirsql import DirSQL
from starlette.datastructures import QueryParams
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

from labnotes.daemon.reads import Reads
from labnotes.daemon.sse import sse
from labnotes.load_experiment import load_experiment
from labnotes.tui.native_rows import native_rows

RELOAD = frozenset({"runs", "experiment_configs"})


class ViewReads:
    """Stream the experiment as views see it, then each change."""

    def __init__(self, root: Path, tables: DirSQL, name: str) -> None:
        self.root = root
        self.tables = tables
        self.name = name
        self.routes = [Route("/experiment", self.experiment)]

    async def state(self) -> dict[str, Any] | None:
        loaded = await load_experiment(self.tables, self.root, self.name, QueryParams())
        if loaded is None:
            return None
        return {
            "name": self.name,
            "config": loaded["config"],
            "views": loaded["views"],
            "runs": list(native_rows(loaded)),
        }

    async def experiment(self, request: Request) -> Response:
        """Send state, then `paths` for changed run files and fresh state on reloads.

        Changes that land while a reload runs collapse into one more reload.
        """
        last = request.headers.get("last-event-id")

        async def stream() -> AsyncIterator[str]:
            await self.tables.ready()
            changes = self.tables.watch()
            wake = asyncio.Event()
            stale = False
            paths: dict[str, None] = {}

            async def mark() -> None:
                nonlocal stale
                async for change in changes:
                    if change.table == "run_files":
                        row = change.row or change.old_row or {}
                        paths[str(row.get("path"))] = None
                        wake.set()
                    elif change.table in RELOAD:
                        stale = True
                        wake.set()

            marker = asyncio.create_task(mark())
            marker.add_done_callback(lambda _: wake.set())
            try:
                shown = await self.state()
                if last != Reads.state_id({"state": shown}):
                    yield sse(shown, "state", Reads.state_id({"state": shown}))
                while True:
                    await wake.wait()
                    wake.clear()
                    if paths:
                        changed = list(paths)
                        paths.clear()
                        yield sse(changed, "paths", Reads.state_id({"state": shown}))
                    if stale:
                        stale = False
                        latest = await self.state()
                        if latest != shown:
                            shown = latest
                            yield sse(shown, "state", Reads.state_id({"state": shown}))
                    if marker.done():
                        break
            finally:
                marker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await marker

        return StreamingResponse(stream(), media_type="text/event-stream")
