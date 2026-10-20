from labnotes.invocation_started import invocation_started


def test_reads_the_utc_stamp_at_the_start_of_the_name() -> None:
    assert invocation_started("20261020-105052-weathered-lake") == (
        "2026-10-20 10:50:52"
    )


def test_has_no_start_without_a_stamp() -> None:
    assert invocation_started("weathered-lake") is None
    assert invocation_started("x20261020-105052") is None
