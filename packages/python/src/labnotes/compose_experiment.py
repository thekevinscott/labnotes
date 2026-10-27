def compose_experiment(
    base: dict[str, object], layer: dict[str, object]
) -> dict[str, object]:
    composed = {**base, **layer}
    for key in ("params", "env"):
        base_values, layer_values = base.get(key), layer.get(key)
        if isinstance(base_values, dict) and isinstance(layer_values, dict):
            composed[key] = {**base_values, **layer_values}
    return composed
