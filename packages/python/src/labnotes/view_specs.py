def view_specs(config: dict[str, object] | None) -> dict[str, str]:
    """Name each view in `[views]`, in config order. `runs` is the column script."""
    views = (config or {}).get("views")
    if not isinstance(views, dict):
        return {}
    return {
        name: spec
        for name, spec in views.items()
        if name != "runs" and isinstance(spec, str)
    }
