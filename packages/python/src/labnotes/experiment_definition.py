import tomlkit


def experiment_definition(
    text: str,
    source: str | None,
    command: str | None,
    repeats: int | None,
    params: dict[str, list[object]],
) -> str:
    document = tomlkit.parse(text)
    document.pop("from", None)
    if command is not None:
        document["command"] = command
    if repeats is not None:
        document["repeats"] = repeats
    if params:
        table = document.setdefault("params", tomlkit.table())
        for name, values in params.items():
            table[name] = values
    head = "" if source is None else tomlkit.dumps({"from": source})
    return head + tomlkit.dumps(document)
