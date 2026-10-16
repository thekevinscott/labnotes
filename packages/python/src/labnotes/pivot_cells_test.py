from labnotes.pivot_cells import pivot_cells


def test_puts_the_last_varies_key_across_the_columns() -> None:
    varies: dict[str, list[object]] = {
        "lang": ["py", "js"],
        "effort": ["low", "mid", "high"],
    }
    cells: list[dict[str, object]] = [
        {"values": {"lang": lang, "effort": effort}, "runs": 0, "completed": 0}
        for lang in varies["lang"]
        for effort in varies["effort"]
    ]

    pivot = pivot_cells(varies, cells)

    assert pivot is not None
    assert pivot["row_keys"] == ["lang"]
    assert pivot["column_key"] == "effort"
    assert pivot["columns"] == ["low", "mid", "high"]
    rows = pivot["rows"]
    assert isinstance(rows, list)
    [py, js] = rows
    assert py["labels"] == ["py"]
    assert js["labels"] == ["js"]
    assert [cell["values"]["effort"] for cell in js["cells"]] == ["low", "mid", "high"]


def test_returns_none_without_a_grid() -> None:
    assert pivot_cells({}, []) is None
    assert pivot_cells({"x": [1]}, []) is None
