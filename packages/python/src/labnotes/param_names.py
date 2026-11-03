from collections.abc import Mapping
from typing import cast

from labnotes.summarize_config import summarize_config


def param_names(config: Mapping[str, object] | None) -> list[str]:
    summary = summarize_config(None if config is None else dict(config))
    return [key for key in cast(dict[str, object], summary["varies"]) if key != "id"]
