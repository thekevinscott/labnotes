from labnotes.retries import (
    DEFAULT_RETRIES,
    RETRY_EXIT_CODE,
    RETRY_EXIT_CODES,
    RETRY_SECONDS,
)


def test_retries_ex_tempfail_three_times_after_thirty_seconds() -> None:
    assert (RETRY_EXIT_CODE, DEFAULT_RETRIES, RETRY_SECONDS) == (75, 3, 30.0)


def test_retries_only_ex_tempfail_by_default() -> None:
    assert RETRY_EXIT_CODES == (75,)
