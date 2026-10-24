import json

import pytest

from labnotes.tui.format_cell import format_cell


@pytest.mark.parametrize(
    ("value", "live", "mark", "style"),
    [
        ("passed", False, "✓", "green"),
        ("failed", False, "✕", "red"),
        ("unfinished", True, "◐", "yellow"),
        ("unfinished", False, "–", "dim"),
    ],
)
def test_marks_the_status(value: str, live: bool, mark: str, style: str) -> None:
    cell = format_cell("status", value, live)

    assert str(cell) == mark
    assert getattr(cell, "style") == style


def test_shows_another_status_as_text() -> None:
    assert format_cell("status", "odd", False) == "odd"


def test_formats_a_duration_in_seconds() -> None:
    assert format_cell("duration", 65, False) == "1m 05s"


@pytest.mark.parametrize(
    ("value", "shown"), [(None, "—"), ("fast", "fast"), (True, "true")]
)
def test_leaves_a_duration_that_isnt_seconds(value: object, shown: str) -> None:
    assert format_cell("duration", value, False) == shown


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("2026-10-17T00:00:01.000Z", "2026-10-17 00:00:01"),
        ("2026-10-17T02:00:01+02:00", "2026-10-17 00:00:01"),
        ("2026-10-17T00:00:01", "2026-10-17 00:00:01"),
        ("yesterday", "yesterday"),
        (None, "—"),
    ],
)
def test_shows_the_start_in_utc(value: object, shown: str) -> None:
    assert format_cell("started", value, False) == shown


def test_formats_other_values() -> None:
    assert format_cell("m", {"a": 1}, False) == '{"a": 1}'
    assert format_cell("m", "2026-10-17T00:00:01Z", False) == "2026-10-17T00:00:01Z"
    assert format_cell("m", 65, False) == "65"


@pytest.mark.parametrize(
    ("pair", "shown"),
    [
        ('["status", "passed"]', "✓"),
        ('["status", "failed"]', "✕"),
        ('["status", "unfinished"]', "–"),
        ('["duration", 65]', "1m 05s"),
        ('["started", "2026-10-17T00:00:01Z"]', "2026-10-17 00:00:01"),
    ],
)
def test_matches_keys_and_values_read_from_json(pair: str, shown: str) -> None:
    key, value = json.loads(pair)

    assert str(format_cell(key, value, False)) == shown


@pytest.mark.parametrize("key", ["a", "zz"])
@pytest.mark.parametrize(
    "value", ["passed", "failed", "unfinished", 65, "2026-10-17T00:00:01Z"]
)
def test_leaves_keys_on_either_side_of_the_special_ones(key: str, value: object) -> None:
    assert format_cell(key, value, False) == str(value)


@pytest.mark.parametrize("value", ["a", "zz"])
def test_leaves_statuses_on_either_side_of_the_known_ones(value: str) -> None:
    assert format_cell("status", value, False) == value
