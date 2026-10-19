import hashlib
from unittest import mock

from labnotes.runner.new_invocation_id import new_invocation_id


def test_hashes_the_time_to_eight_hex_digits() -> None:
    with mock.patch("labnotes.runner.new_invocation_id.time") as time:
        time.time_ns.return_value = 1234

        assert new_invocation_id() == hashlib.sha256(b"1234").hexdigest()[:8]
