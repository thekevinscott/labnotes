from collections.abc import Sequence


def shared_params(
    runs: list[dict[str, object]], params: Sequence[str]
) -> dict[str, object]:
    first, *rest = runs
    return {
        key: first[key] for key in params if all(run[key] == first[key] for run in rest)
    }
