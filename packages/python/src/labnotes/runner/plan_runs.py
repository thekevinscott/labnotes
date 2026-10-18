def plan_runs(
    cells: list[dict[str, object]], repeats: int, finished: list[dict[str, object]]
) -> list[dict[str, object]]:
    return [
        cell
        for round_ in range(repeats)
        for cell in cells
        if round_ < repeats - finished.count(cell)
    ]
