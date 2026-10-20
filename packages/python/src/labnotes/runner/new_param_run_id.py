import secrets
from collections.abc import Callable

from labnotes.runner.new_run_id import new_run_id
from labnotes.runner.param_run_name import param_run_name


def new_param_run_id(
    params: dict[str, object],
    choices: dict[str, list[object]],
    taken: Callable[[str], bool],
) -> str:
    name = param_run_name(params, choices)
    if not name:
        return new_run_id(taken)
    while taken(candidate := f"{name}-{secrets.token_hex(2)}"):
        pass
    return candidate
