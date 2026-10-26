from unittest import mock

from labnotes.grid_cell import grid_cell


def test_links_to_the_table_filtered_to_the_cell() -> None:
    with mock.patch(
        "labnotes.grid_cell.format_value", side_effect=lambda value: f"<{value}>"
    ):
        cell = grid_cell({"model": "a", "lang": "en"}, {"runs": 3, "completed": 2})

    assert cell == {
        "values": {"model": "a", "lang": "en"},
        "runs": 3,
        "completed": 2,
        "href": "?f.model=%3Ca%3E&f.lang=%3Cen%3E#runs",
    }


def test_counts_nothing_for_a_cell_without_runs() -> None:
    cell = grid_cell({}, {})

    assert cell == {"values": {}, "runs": 0, "completed": 0, "href": "?#runs"}
