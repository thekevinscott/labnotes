import asyncio
from unittest import mock

import pytest

from labnotes.stop_idle_kernels import stop_idle_kernels


def test_checks_every_kernel_once_a_minute() -> None:
    first, second = mock.Mock(), mock.Mock()
    for kernel in (first, second):
        kernel.stop_if_idle = mock.AsyncMock()
    with mock.patch(
        "labnotes.stop_idle_kernels.asyncio.sleep",
        new_callable=mock.AsyncMock,
        side_effect=[None, None, asyncio.CancelledError],
    ) as sleep:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(stop_idle_kernels({("e", "a"): first, ("e", "b"): second}, 30))

    assert sleep.await_args_list == [mock.call(60)] * 3
    for kernel in (first, second):
        assert kernel.stop_if_idle.await_args_list == [mock.call(1800)] * 2


def test_tolerates_kernels_added_while_checking() -> None:
    kernels: dict[tuple[str, str], mock.Mock] = {}

    async def add_another(idle_seconds: float) -> None:
        kernels[("e", "new")] = mock.Mock()

    kernels[("e", "a")] = mock.Mock(stop_if_idle=add_another)
    with mock.patch(
        "labnotes.stop_idle_kernels.asyncio.sleep",
        new_callable=mock.AsyncMock,
        side_effect=[None, asyncio.CancelledError],
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(stop_idle_kernels(kernels, 30))

    assert ("e", "new") in kernels
