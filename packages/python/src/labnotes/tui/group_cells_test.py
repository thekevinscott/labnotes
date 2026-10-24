import json
from typing import Any

from labnotes.tui.group_cells import group_cells

KEYS = ["status", "id", "runs", "m", "n", "started", "x", "duration"]
COLUMNS = [{"key": key, "label": key.upper()} for key in KEYS]


def group(**fields: object) -> dict[str, Any]:
    return {
        "name": "20261017-000000",
        "started": "2026-10-17 00:00:00",
        "runs": [{}, {}, {}],
        "shared": {"m": "a", "x": 5},
        "passed": 2,
        "failed": 1,
        "unfinished": 0,
        **fields,
    }


def test_summarizes_an_invocation() -> None:
    assert [str(cell) for cell in group_cells(group(), COLUMNS, False, False)] == [
        "2✓ 1✕",
        "▸ 20261017-000000",
        "3",
        "a",
        "",
        "2026-10-17 00:00:00",
        "5",
        "",
    ]


def test_follows_the_column_order() -> None:
    columns = [COLUMNS[3], COLUMNS[1]]

    assert group_cells(group(), columns, False, False) == ["a", "▸ 20261017-000000"]


def test_leaves_the_start_blank_when_the_name_has_no_stamp() -> None:
    assert group_cells(group(started=None), COLUMNS, False, False)[5] == ""


def test_formats_shared_values() -> None:
    cells = group_cells(group(shared={"m": None, "n": True}), COLUMNS, False, False)

    assert cells[3:5] == ["—", "true"]


def styles(status: Any) -> list[tuple[str, str]]:
    return [
        (status.plain[span.start : span.end], str(span.style)) for span in status.spans
    ]


def test_colors_the_counts() -> None:
    [status, *_] = group_cells(group(), COLUMNS, False, False)

    assert styles(status) == [("2✓", "green"), ("1✕", "red")]


def test_counts_running_runs_while_the_daemon_is_up() -> None:
    [status, *_] = group_cells(group(unfinished=4), COLUMNS, True, False)

    assert str(status) == "2✓ 1✕ 4◐"
    assert styles(status)[-1] == (" 4◐", "yellow")


def test_counts_interrupted_runs_once_the_daemon_is_down() -> None:
    [status, *_] = group_cells(group(unfinished=4), COLUMNS, False, False)

    assert str(status) == "2✓ 1✕ 4–"
    assert styles(status)[-1] == (" 4–", "dim")


def test_marks_an_open_invocation() -> None:
    assert group_cells(group(), COLUMNS, False, True)[1] == "▾ 20261017-000000"


def test_matches_keys_read_from_json() -> None:
    columns = [{"key": key, "label": key} for key in json.loads(json.dumps(KEYS))]

    assert [str(cell) for cell in group_cells(group(), columns, False, False)][:6] == [
        "2✓ 1✕",
        "▸ 20261017-000000",
        "3",
        "a",
        "",
        "2026-10-17 00:00:00",
    ]
