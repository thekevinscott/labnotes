from labnotes.format_started import format_started


def test_marks_a_utc_time_for_the_browser_to_localize() -> None:
    assert format_started("2026-10-17 00:00:01") == (
        '<time datetime="2026-10-17T00:00:01Z">2026-10-17 00:00:01</time>'
    )


def test_escapes_the_time() -> None:
    assert "<b>" not in format_started("<b>")


def test_shows_a_dash_when_there_is_no_time() -> None:
    assert format_started(None) == "—"
