from collections.abc import Mapping

from labnotes.models import RunView

STATUSES = {"complete", "incomplete"}


def parse_run_view(params: Mapping[str, str], columns: list[str]) -> RunView:
    sort = params.get("sort")
    status = params.get("status")
    return RunView(
        sort=sort if sort in columns or sort == "status" else None,
        descending=params.get("order") == "desc",
        status=status if status in STATUSES else None,
        filters={
            column: value
            for column in columns
            if (value := params.get(f"f.{column}", "").strip())
        },
    )
