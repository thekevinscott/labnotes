from labnotes.format_value import format_value


def check_subset(params: dict[str, list[object]], only: dict[str, str]) -> None:
    for param, value in only.items():
        if param not in params:
            declared = ", ".join(params) or "none"
            raise ValueError(f"No param {param}. Params: {declared}.")
        values = [format_value(option) for option in params[param]]
        if value not in values:
            raise ValueError(
                f"No value {value} for {param}. Values: {', '.join(values)}."
            )
