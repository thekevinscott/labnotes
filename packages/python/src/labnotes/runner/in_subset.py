from labnotes.format_value import format_value


def in_subset(cell: dict[str, object], only: dict[str, list[str]]) -> bool:
    return all(format_value(cell[param]) in values for param, values in only.items())
