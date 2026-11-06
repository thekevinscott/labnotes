def plan_runs(
    cells: list[dict[str, object]], repeats: int, finished: list[dict[str, object]]
) -> list[dict[str, object]]:
    unique = [cell for i, cell in enumerate(cells) if cell not in cells[:i]]
    needed = [repeats * cells.count(cell) - finished.count(cell) for cell in unique]
    return [
        cell
        for round_ in range(max(needed, default=0))
        for cell, count in zip(unique, needed, strict=True)
        if round_ < count
    ]
