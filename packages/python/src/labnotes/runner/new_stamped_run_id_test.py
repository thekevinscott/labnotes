from collections.abc import Iterator
from datetime import UTC, datetime
from unittest import mock

import pytest

from labnotes.runner.new_stamped_run_id import new_stamped_run_id


@pytest.fixture(autouse=True)
def now() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.runner.new_stamped_run_id.datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 20, 0, 4, 29, tzinfo=UTC)
        yield clock


@pytest.fixture(autouse=True)
def new_run_id() -> Iterator[mock.MagicMock]:
    with mock.patch(
        "labnotes.runner.new_stamped_run_id.new_run_id", return_value="brave-fox"
    ) as new_run_id:
        yield new_run_id


def test_prefixes_the_name_with_utc_start_time(now: mock.MagicMock) -> None:
    assert new_stamped_run_id(lambda _: False) == "20261020-000429-brave-fox"
    now.now.assert_called_once_with(UTC)


def test_checks_clashes_against_the_stamped_name(
    new_run_id: mock.MagicMock,
) -> None:
    taken = mock.Mock(return_value=True)
    new_stamped_run_id(taken)

    assert new_run_id.call_args.args[0]("brave-fox") is True
    taken.assert_called_once_with("20261020-000429-brave-fox")
