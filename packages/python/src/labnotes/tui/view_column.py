def view_column(entry: object) -> dict[str, str]:
    if isinstance(entry, str):
        return {"key": entry, "label": entry}
    if not isinstance(entry, dict):
        raise ValueError("a column must be a string or an object")
    key = entry.get("key")
    if not isinstance(key, str):
        raise ValueError("a column needs a string key")
    label = entry.get("label", key)
    if not isinstance(label, str):
        raise ValueError(f"column {key}: label must be a string")
    unknown = sorted(entry.keys() - {"key", "label"})
    if unknown:
        raise ValueError(f"column {key}: unknown fields {', '.join(unknown)}")
    return {"key": key, "label": label}
