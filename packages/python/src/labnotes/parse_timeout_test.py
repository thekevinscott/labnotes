from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.parse_timeout import parse_timeout


class BadParameter(Exception):
    pass


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with (
        mock.patch("labnotes.parse_timeout.parse") as parse,
        mock.patch(
            "labnotes.parse_timeout.click", mock.Mock(BadParameter=BadParameter)
        ),
    ):
        yield {"parse": parse}


def call(value: str | None) -> float | None:
    return parse_timeout(mock.Mock(), mock.Mock(), value)


def test_leaves_an_unset_timeout_unset(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert call(None) is None
    collaborators["parse"].assert_not_called()


@pytest.mark.parametrize("seconds", [1, 90, 1.5, 0.001])
def test_returns_the_seconds_parsed(
    seconds: float, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["parse"].return_value = seconds

    assert call("given") == seconds
    collaborators["parse"].assert_called_once_with("given")


@pytest.mark.parametrize("parsed", [None, 0, 0.0, -300])
def test_rejects_anything_but_a_positive_duration(
    parsed: float | None, collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["parse"].return_value = parsed

    with pytest.raises(BadParameter) as raised:
        call("soon")
    assert str(raised.value) == (
        "'soon': use a duration over 0, like 90, 30s, 10m or 1h30m."
    )
