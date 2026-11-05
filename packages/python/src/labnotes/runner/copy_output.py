import asyncio
import json
import os
import time
from typing import BinaryIO

CHUNK_BYTES = 1 << 16


async def copy_output(fd: int, stream: str, log: BinaryIO, index: BinaryIO) -> None:
    reader = asyncio.StreamReader()
    transport, _ = await asyncio.get_running_loop().connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), os.fdopen(fd, "rb")
    )
    end = 0
    try:
        while chunk := await reader.read(CHUNK_BYTES):
            log.write(chunk)
            log.flush()
            end += len(chunk)
            entry = {"stream": stream, "end": end, "time": time.time()}
            index.write(json.dumps(entry).encode() + b"\n")
            index.flush()
    finally:
        transport.close()
