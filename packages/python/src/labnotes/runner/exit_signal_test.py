import signal

import pytest

from labnotes.runner.exit_signal import exit_signal


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (-9, 9),
        (-15, 15),
        (137, 9),
        (143, 15),
        (129, 1),
        (127 + signal.NSIG, signal.NSIG - 1),
        (0, None),
        (1, None),
        (75, None),
        (128, None),
        (128 + signal.NSIG, None),
        (255, None),
        (None, None),
    ],
)
def test_reads_the_signal_from_an_exit_code(
    exit_code: int | None, expected: int | None
) -> None:
    assert exit_signal(exit_code) == expected
