from labnotes.format_value import format_value


def in_subset(cell: dict[str, object], only: dict[str, str]) -> bool:
    return all(format_value(cell[param]) == value for param, value in only.items())
