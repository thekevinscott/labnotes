from collections.abc import Mapping

from labnotes.param_names import param_names


def run_columns(config: Mapping[str, object] | None) -> list[str]:
    return ["id", *param_names(config), "started", "duration"]
