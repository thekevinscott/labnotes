from labnotes.pivot_runs import pivot_runs


def test_puts_the_last_axis_across_and_the_rest_down() -> None:
    axes: dict[str, list[object]] = {"model": ["a", "b"], "lang": ["en", "fr"]}
    counts: list[dict[str, object]] = [
        {"model": "a", "lang": "fr", "runs": 3, "completed": 2},
    ]

    grid = pivot_runs(axes, counts)

    assert grid["row_keys"] == ["model"]
    assert grid["column_key"] == "lang"
    assert grid["columns"] == ["en", "fr"]
    rows = grid["rows"]
    assert [row["labels"] for row in rows] == [["a"], ["b"]]
    first = rows[0]["cells"]
    assert first[0] == {
        "values": {"model": "a", "lang": "en"},
        "runs": 0,
        "completed": 0,
        "href": "?f.model=a&f.lang=en#runs",
    }
    assert first[1]["runs"] == 3
    assert first[1]["completed"] == 2


def test_crosses_every_leading_axis_into_rows() -> None:
    axes: dict[str, list[object]] = {"a": [1, 2], "b": ["x", "y"], "c": [True, False]}

    grid = pivot_runs(axes, [])

    assert grid["row_keys"] == ["a", "b"]
    assert [row["labels"] for row in grid["rows"]] == [
        [1, "x"],
        [1, "y"],
        [2, "x"],
        [2, "y"],
    ]
    assert grid["rows"][0]["cells"][0]["href"] == "?f.a=1&f.b=x&f.c=true#runs"


def test_matches_booleans_to_the_integers_sql_returns() -> None:
    axes: dict[str, list[object]] = {"flag": [True, False]}
    counts: list[dict[str, object]] = [{"flag": 1, "runs": 1, "completed": 1}]

    [row] = pivot_runs(axes, counts)["rows"]

    assert row["labels"] == []
    assert [cell["completed"] for cell in row["cells"]] == [1, 0]


def test_one_cell_when_nothing_varies() -> None:
    grid = pivot_runs({}, [{"runs": 4, "completed": 3}])

    assert grid["row_keys"] == []
    assert grid["column_key"] is None
    [row] = grid["rows"]
    [cell] = row["cells"]
    assert cell == {"values": {}, "runs": 4, "completed": 3, "href": "?#runs"}
