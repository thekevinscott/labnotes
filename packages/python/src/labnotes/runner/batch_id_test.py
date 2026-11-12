import os
from unittest import mock

from labnotes.runner.batch_id import batch_id


def test_names_a_batch_by_time_process_and_a_unique_nonce() -> None:
    with mock.patch(
        "labnotes.runner.batch_id.time.gmtime",
        return_value=(2026, 11, 11, 1, 2, 3, 0, 0, 0),
    ):
        first = batch_id()
    stamp, pid, nonce = first.rsplit("-", 2)
    assert stamp == "20261111-010203"
    assert pid == str(os.getpid())
    assert len(nonce) == 8
    assert all(character in "0123456789abcdef" for character in nonce)
    assert batch_id() != batch_id()


def test_a_batch_id_is_not_a_path() -> None:
    assert "/" not in batch_id()
