def plan_runs(
    cells: list[dict[str, object]], repeats: int, finished: list[dict[str, object]]
) -> list[dict[str, object]]:
    unique = [cell for i, cell in enumerate(cells) if cell not in cells[:i]]
    slots = [
        (round_, cell)
        for cell in unique
        for round_ in range(repeats * cells.count(cell) - finished.count(cell))
    ]
    return [cell for _, cell in sorted(slots, key=lambda slot: slot[0])]
