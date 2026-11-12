"""Follow a live daemon's batches and events over its event stream."""

import json
from collections.abc import AsyncIterator
from typing import Self, cast

import httpx2

from labnotes.daemon.client import daemon_socket
from labnotes.models import LabnotesConfig

STREAM_LIMIT = 16 * 1024 * 1024


class Attachment:
    """Hold one open event stream; its first event names the active batches."""

    def __init__(
        self,
        client: httpx2.AsyncClient,
        response: httpx2.Response,
        events: AsyncIterator[httpx2.ServerSentEvent],
        batches: list[str],
    ) -> None:
        self.client = client
        self.response = response
        self.events = events
        self.batches = batches

    @classmethod
    async def open(cls, config: LabnotesConfig, name: str) -> Self:
        path = daemon_socket(config, name)
        if path is None:
            raise ValueError(f"No daemon is running for {name}.")
        client = httpx2.AsyncClient(
            transport=httpx2.AsyncHTTPTransport(uds=str(path)),
            base_url="http://labnotes",
            timeout=httpx2.Timeout(10, read=None),
        )
        try:
            response = await client.send(
                client.build_request("GET", "/events"), stream=True
            )
            if response.is_error:
                rejected = json.loads(await response.aread())
                raise ValueError(str(rejected.get("error", "Daemon rejected attach")))
            events = aiter(httpx2.EventSource(response, max_event_size=STREAM_LIMIT))
            first = await anext(events)
            batches = cast(list[str], cast(dict[str, object], first.json())["batches"])
        except (httpx2.HTTPError, StopAsyncIteration) as error:
            await client.aclose()
            raise ValueError(
                str(error) or f"Daemon for {name} closed without a reply."
            ) from error
        except BaseException:
            await client.aclose()
            raise
        return cls(client, response, events, batches)

    async def __aiter__(self) -> AsyncIterator[tuple[str, dict[str, object]]]:
        try:
            async for event in self.events:
                message = cast(dict[str, object], event.json())
                yield str(message["batch"]), cast(dict[str, object], message["event"])
        except (httpx2.HTTPError, httpx2.StreamError) as error:
            raise ValueError(str(error)) from error

    async def aclose(self) -> None:
        await self.response.aclose()
        await self.client.aclose()
