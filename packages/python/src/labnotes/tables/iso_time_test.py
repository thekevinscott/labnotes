from labnotes.tables.iso_time import iso_time


def test_formats_unix_seconds_as_utc() -> None:
    assert iso_time(0) == "1970-01-01T00:00:00Z"
    assert iso_time(1_792_281_600.9) == "2026-10-18T00:00:00Z"
