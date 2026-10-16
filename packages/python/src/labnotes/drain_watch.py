from dirsql import DirSQL


async def drain_watch(db: DirSQL) -> None:
    async for _ in db.watch():
        pass
