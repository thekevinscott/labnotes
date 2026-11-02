import tomlkit


def experiment_definition(
    text: str,
    source: str | None,
    command: str | None,
    repeats: int | None,
    params: dict[str, list[object]],
    continues: bool = False,
) -> str:
    document = tomlkit.parse(text)
    document.pop("from", None)
    document.pop("mode", None)
    if command is not None:
        document["command"] = command
    if repeats is not None:
        document["repeats"] = repeats
    if "continues" not in document:
        document["continues"] = continues
    if params:
        table = document.setdefault("params", tomlkit.table())
        for name, values in params.items():
            table[name] = values
    head = "" if source is None else tomlkit.dumps({"from": source})
    return head + tomlkit.dumps(document)
