from collections.abc import Sequence


def shared_params(
    runs: list[dict[str, object]], params: Sequence[str]
) -> dict[str, object]:
    return {
        key: runs[0][key]
        for key in params
        if all(run[key] == runs[0][key] for run in runs)
    }
