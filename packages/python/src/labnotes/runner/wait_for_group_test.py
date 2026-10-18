import asyncio
from unittest import mock

from labnotes.runner.wait_for_group import wait_for_group


def test_polls_until_the_group_is_gone() -> None:
    with (
        mock.patch(
            "labnotes.runner.wait_for_group.os.killpg",
            side_effect=[None, None, ProcessLookupError],
        ) as killpg,
        mock.patch(
            "labnotes.runner.wait_for_group.asyncio.sleep", new=mock.AsyncMock()
        ) as sleep,
    ):
        asyncio.run(wait_for_group(42))

    assert killpg.call_args_list == [mock.call(42, 0)] * 3
    assert sleep.await_args_list == [mock.call(0.1)] * 2
