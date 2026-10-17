from collections.abc import Iterator
from unittest import mock

import pytest

from labnotes.runner.new_run_id import new_run_id


@pytest.fixture(autouse=True)
def haikunator() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.runner.new_run_id.Haikunator") as haikunator:
        haikunator.return_value.haikunate.return_value = "brave-fox"
        yield haikunator


def test_names_a_run_like_a_haiku(haikunator: mock.MagicMock) -> None:
    assert new_run_id(lambda _: False) == "brave-fox"
    haikunator.return_value.haikunate.assert_called_once_with(token_length=0)


def test_adds_a_suffix_on_a_clash() -> None:
    taken = {"brave-fox", "brave-fox-2"}

    assert new_run_id(taken.__contains__) == "brave-fox-3"
