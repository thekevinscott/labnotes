import pytest

from labnotes.tui.run_cells import run_cells

COLUMNS = ["count", "id", "m", "started", "duration"]


def run(**fields: object) -> dict[str, object]:
    return {
        "labnotes_completed": 1,
        "labnotes_unfinished": 0,
        "count": 5,
        "id": "inv/r1",
        "m": "a",
        "started": "2026-10-17 00:00:00",
        "duration": 65,
        **fields,
    }


def plain(cells: list[object]) -> list[str]:
    return [str(cell) for cell in cells]


def test_shows_a_flat_run() -> None:
    assert plain(run_cells(run(), COLUMNS, False, False)) == [
        "✓",
        "5",
        "inv/r1",
        "a",
        "2026-10-17 00:00:00",
        "1m 05s",
    ]


def test_indents_a_nested_run_under_its_invocation() -> None:
    assert plain(run_cells(run(), COLUMNS, True, False)) == [
        "✓",
        "5",
        "  r1",
        "",
        "a",
        "2026-10-17 00:00:00",
        "1m 05s",
    ]


def test_shows_a_lone_nested_run_by_its_whole_id() -> None:
    assert plain(run_cells(run(id="lone"), COLUMNS, True, False))[2:4] == ["lone", ""]


def test_fills_missing_values_with_a_dash() -> None:
    cells = plain(run_cells(run(m=None, duration=None), COLUMNS, False, False))

    assert cells[3] == "—"
    assert cells[5] == "—"


@pytest.mark.parametrize(
    ("fields", "live", "mark", "style"),
    [
        ({}, False, "✓", "green"),
        ({"labnotes_completed": 0}, False, "✕", "red"),
        ({"labnotes_completed": 0, "labnotes_unfinished": 1}, True, "◐", "yellow"),
        ({"labnotes_completed": 0, "labnotes_unfinished": 1}, False, "–", "dim"),
    ],
)
def test_marks_the_status(
    fields: dict[str, object], live: bool, mark: str, style: str
) -> None:
    [status, *_] = run_cells(run(**fields), COLUMNS, False, live)

    assert str(status) == mark
    assert getattr(status, "style") == style
