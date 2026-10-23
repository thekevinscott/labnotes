from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.runner.exit_signal import exit_signal


@pytest.fixture(autouse=True)
def nsig() -> Iterator[None]:
    with mock.patch("labnotes.runner.exit_signal.signal", mock.Mock(NSIG=65)):
        yield


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (-1, 1),
        (-9, 9),
        (-15, 15),
        (137, 9),
        (143, 15),
        (129, 1),
        (192, 64),
        (0, None),
        (1, None),
        (75, None),
        (128, None),
        (193, None),
        (255, None),
        (None, None),
    ],
)
def test_reads_the_signal_from_an_exit_code(
    exit_code: int | None, expected: int | None
) -> None:
    assert exit_signal(exit_code) == expected
