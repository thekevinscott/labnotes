from itertools import product


def _key(value: object) -> object:
    return int(value) if isinstance(value, bool) else value


def cell_progress(
    varies: dict[str, list[object]], counts: list[dict[str, object]]
) -> list[dict[str, object]]:
    by_cell = {tuple(_key(row[key]) for key in varies): row for row in counts}
    cells = []
    for values in product(*varies.values()):
        row = by_cell.get(tuple(_key(value) for value in values), {})
        cells.append(
            {
                "values": dict(zip(varies, values)),
                "runs": row.get("runs", 0),
                "completed": row.get("completed", 0),
            }
        )
    return cells
