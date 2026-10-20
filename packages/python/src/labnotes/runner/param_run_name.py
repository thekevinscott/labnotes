import os
import re

UNSAFE = re.compile(r"[^A-Za-z0-9]+")
LIMIT = 60


def param_run_name(params: dict[str, object], choices: dict[str, list[object]]) -> str:
    parts = []
    for name, values in choices.items():
        if len(values) < 2:
            continue
        shared = os.path.commonprefix([str(value) for value in values])
        cut = re.match(r".*[^A-Za-z0-9]", shared)
        value = str(params[name])[cut.end() if cut else 0 :]
        parts.append(UNSAFE.sub("-", value).strip("-"))
    return "-".join(part for part in parts if part)[:LIMIT].strip("-")
