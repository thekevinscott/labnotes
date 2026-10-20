import asyncio
from pathlib import Path

from conftest import write

from labnotes.read_config import read_config
from labnotes.tables.open_tables import open_tables


def test_reports_each_of_two_edits_in_the_same_second(tmp_path: Path) -> None:
    write(tmp_path / ".labnotes.toml", "")
    note = tmp_path / "alpha/files/plan.md"
    write(note, "one")

    async def watch() -> list[str]:
        tables = open_tables(read_config(tmp_path / ".labnotes.toml"))
        events = tables.watch()
        updates: list[str] = []

        async def collect() -> None:
            async for event in events:
                if event.table == "files" and event.action == "update":
                    updates.append(str(event.file_path))
                    if len(updates) == 2:
                        return

        collecting = asyncio.create_task(collect())
        await tables.ready()
        await asyncio.sleep(0.5)
        write(note, "two")
        await asyncio.sleep(0.3)
        write(note, "three")
        await asyncio.wait_for(collecting, 10)
        return updates

    assert len(asyncio.run(watch())) == 2
