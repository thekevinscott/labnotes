from collections.abc import Mapping

from starlette.datastructures import ImmutableMultiDict

from labnotes.models import RunView

STATUSES = {"complete", "incomplete"}


def parse_run_view(
    params: ImmutableMultiDict[str, str],
    columns: list[str],
    choices: Mapping[str, Mapping[str, str]],
) -> RunView:
    sort = params.get("sort")
    status = params.get("status")
    return RunView(
        sort=sort if sort in columns or sort == "status" else None,
        descending=params.get("order") == "desc",
        status=status if status in STATUSES else None,
        filters={
            column: value
            for column in columns
            if column not in choices
            and (value := params.get(f"f.{column}", "").strip())
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
