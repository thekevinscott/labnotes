from labnotes.retries import DEFAULT_RETRIES, RETRY_EXIT_CODE, RETRY_SECONDS


def test_retries_ex_tempfail_twice_after_thirty_seconds() -> None:
    assert (RETRY_EXIT_CODE, DEFAULT_RETRIES, RETRY_SECONDS) == (75, 2, 30.0)
