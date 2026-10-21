def compose_experiment(
    base: dict[str, object], layer: dict[str, object]
) -> dict[str, object]:
    composed = {**base, **layer}
    base_params, layer_params = base.get("params"), layer.get("params")
    if isinstance(base_params, dict) and isinstance(layer_params, dict):
        composed["params"] = {**base_params, **layer_params}
    return composed
