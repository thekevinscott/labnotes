import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from labnotes.daemon.view_reads import ViewReads


def ident(value: object) -> str:
    return json.dumps(value, sort_keys=True)


@pytest.fixture(autouse=True)
def state_ids() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.daemon.view_reads.Reads") as found:
        found.state_id.side_effect = ident
        yield found


LOADED = {"config": {"command": "go"}, "views": {"progress": "p.py:P"}}


def change(table: str, row: dict[str, object] | None, old: Any = None) -> Any:
    return SimpleNamespace(table=table, row=row, old_row=old)


def tables(*changes: Any, hold: asyncio.Event | None = None) -> mock.Mock:
    async def watch() -> AsyncIterator[Any]:
        for found in changes:
            yield found
            await asyncio.sleep(0)
        if hold is not None:
            await hold.wait()

    found = mock.Mock()
    found.ready = mock.AsyncMock()
    found.watch = mock.Mock(side_effect=lambda: watch())
    return found


def parse(frame: str) -> tuple[str, str, Any]:
    fields = dict(line.split(": ", 1) for line in frame.splitlines() if line)
    return fields["event"], fields["id"], json.loads(fields["data"])


async def drain(
    reads: ViewReads, last: str | None = None, limit: int = 10
) -> list[tuple[str, str, Any]]:
    headers = {} if last is None else {"last-event-id": last}
    response: Any = await reads.experiment(mock.Mock(headers=headers))
    assert response.media_type == "text/event-stream"
    frames = []
    async for frame in response.body_iterator:
        frames.append(parse(str(frame)))
        if len(frames) == limit:
            break
    return frames


def state(runs: list[str]) -> dict[str, object]:
    return {
        "name": "exp",
        "config": {"command": "go"},
        "views": {"progress": "p.py:P"},
        "runs": [{"status": status} for status in runs],
    }


def test_state_is_none_for_a_missing_experiment(tmp_path: Path) -> None:
    reads = ViewReads(tmp_path, tables(), "exp")
    with mock.patch(
        "labnotes.daemon.view_reads.load_experiment",
        new=mock.AsyncMock(return_value=None),
    ):
        assert asyncio.run(reads.state()) is None
    assert [route.path for route in reads.routes] == ["/experiment"]


def test_state_holds_name_config_views_and_native_rows(tmp_path: Path) -> None:
    found = tables()
    reads = ViewReads(tmp_path, found, "exp")
    with (
        mock.patch(
            "labnotes.daemon.view_reads.load_experiment",
            new=mock.AsyncMock(return_value=LOADED),
        ) as load,
        mock.patch(
            "labnotes.daemon.view_reads.native_rows",
            return_value=({"status": "passed"},),
        ) as native,
    ):
        assert asyncio.run(reads.state()) == state(["passed"])
    assert load.await_args.args[:3] == (found, tmp_path, "exp")
    native.assert_called_once_with(LOADED)


def test_streams_state_then_changed_paths_then_reloads_only_when_it_changes(
    tmp_path: Path,
) -> None:
    found = tables(
        change("run_files", {"path": "exp/runs/a/stdout.log"}),
        change("run_files", None, {"path": "exp/runs/a/old.log"}),
        change("other", {"path": "ignored"}),
        change("runs", {"id": "a"}),
        change("experiment_configs", {"name": "exp"}),
        change("runs", {"id": "a"}),
    )
    reads = ViewReads(tmp_path, found, "exp")
    shown = [state(["running"]), state(["passed"]), state(["passed"])]
    loads = [*shown, *[shown[-1]] * 3]
    with mock.patch.object(reads, "state", new=mock.AsyncMock(side_effect=loads)):
        frames = asyncio.run(drain(reads))
    first_id = ident({"state": shown[0]})
    second_id = ident({"state": shown[1]})
    found.ready.assert_awaited_once_with()
    assert frames[0] == ("state", first_id, shown[0])
    assert ("paths", first_id, ["exp/runs/a/stdout.log"]) in frames
    assert frames[-1] == ("state", second_id, shown[1])
    assert [kind for kind, _, _ in frames].count("state") == 2
    sent = [path for kind, _, data in frames if kind == "paths" for path in data]
    assert sent == ["exp/runs/a/stdout.log", "exp/runs/a/old.log"]


def test_a_resuming_client_gets_state_again(tmp_path: Path) -> None:
    found = tables(change("run_files", {"path": "exp/runs/a/stdout.log"}))
    reads = ViewReads(tmp_path, found, "exp")
    shown = state(["running"])
    current = ident({"state": shown})
    with mock.patch.object(reads, "state", new=mock.AsyncMock(return_value=shown)):
        frames = asyncio.run(drain(reads, current))
    assert frames == [
        ("state", current, shown),
        ("paths", current, ["exp/runs/a/stdout.log"]),
    ]


def test_closing_the_stream_stops_watching(tmp_path: Path) -> None:
    hold = asyncio.Event()
    found = tables(hold=hold)
    reads = ViewReads(tmp_path, found, "exp")

    async def drive() -> None:
        with mock.patch.object(
            reads, "state", new=mock.AsyncMock(return_value=state([]))
        ):
            response: Any = await reads.experiment(mock.Mock(headers={}))
            frames = response.body_iterator
            first = await anext(frames)
            assert parse(str(first))[0] == "state"
            await frames.aclose()

    asyncio.run(drive())
