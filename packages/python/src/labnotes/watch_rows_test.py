import asyncio
from collections.abc import AsyncIterator
from unittest import mock

from labnotes.watch_rows import watch_rows


def event(table: str | None, row: object = None, old_row: object = None) -> mock.Mock:
    return mock.Mock(table=table, row=row, old_row=old_row)


def built(text: str) -> str:
    # A string made at runtime, so `is` against a literal fails where `==` holds.
    return "".join(list(text))


EVENTS = [
    event(built("files"), {"experiment": built("alpha"), "n": 1}),
    event("files", {"experiment": "beta", "n": 2}),
    event("runs", {"experiment": "alpha", "n": 3}),
    event("logs", {"experiment": "alpha", "n": 4}),
    event(None),
    event("runs", None, {"experiment": "alpha", "n": 5}),
]


def collect(*args: object) -> list[object]:
    async def events() -> AsyncIterator[mock.Mock]:
        for each in EVENTS:
            yield each

    tables = mock.Mock()
    tables.watch.return_value = events()

    async def run() -> list[object]:
        return [row["n"] async for row in watch_rows(tables, *args)]  # type: ignore[arg-type]

    return asyncio.run(run())


def test_yields_the_changed_rows_of_the_named_tables_for_one_experiment() -> None:
    assert collect({"files", "runs"}, built("alpha")) == [1, 3, 5]


def test_yields_every_experiments_rows_without_an_experiment() -> None:
    assert collect({"files", "runs"}) == [1, 2, 3, 5]
