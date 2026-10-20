from collections.abc import Mapping

from labnotes.models import QueryParams, RunView

STATUSES = {"complete", "incomplete"}


def parse_run_view(
    params: QueryParams,
    columns: list[str],
    choices: Mapping[str, Mapping[str, str]],
) -> RunView:
    def last(key: str) -> str | None:
        values = params.getlist(key)
        return values[-1] if values else None

    sort = last("sort")
    status = last("status")
    return RunView(
        sort=sort if sort in columns or sort == "status" else None,
        descending=last("order") == "desc",
        status=status if status in STATUSES else None,
        filters={
            column: value
            for column in columns
            if column not in choices and (value := (last(f"f.{column}") or "").strip())
        },
        picked={
            column: picked
            for column, values in choices.items()
            if (
                picked := {
                    label: values[label]
                    for label in params.getlist(f"f.{column}")
                    if label in values
                }
            )
        },
    )
