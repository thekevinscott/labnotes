def plan_runs(
    cells: list[dict[str, object]], repeats: int, finished: list[dict[str, object]]
) -> list[dict[str, object]]:
    shortfalls = [repeats - finished.count(cell) for cell in cells]
    return [
        cell
        for round_ in range(repeats)
        for cell, shortfall in zip(cells, shortfalls, strict=True)
        if round_ < shortfall
    ]
