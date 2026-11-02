from collections.abc import Mapping

from labnotes.run_columns import run_columns


def table_columns(config: Mapping[str, object]) -> list[dict[str, str]]:
    keys = run_columns(config)
    return [{"key": "status", "label": ""}, *({"key": k, "label": k} for k in keys)]
