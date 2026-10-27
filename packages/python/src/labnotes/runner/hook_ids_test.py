import pytest

from labnotes.runner.hook_ids import hook_ids


def test_gives_both_ids_when_one_run_is_planned() -> None:
    hooks: dict[str, str | None] = {"setup": "up {run_id}", "teardown": None}

    assert hook_ids(hooks, "inv", ["r1"]) == {"run_id": "r1", "invocation_id": "inv"}


def test_gives_only_the_invocation_id_to_hooks_without_run_id() -> None:
    hooks: dict[str, str | None] = {"setup": "up {invocation_id}", "teardown": None}

    assert hook_ids(hooks, "inv", ["r1", "r2"]) == {"invocation_id": "inv"}


@pytest.mark.parametrize("runs", [[], ["r1", "r2"]])
def test_rejects_run_id_unless_one_run_is_planned(runs: list[str]) -> None:
    hooks: dict[str, str | None] = {"setup": None, "teardown": "down {run_id}"}

    with pytest.raises(ValueError) as error:
        hook_ids(hooks, "inv", runs)

    assert str(error.value) == (
        f"teardown command down {{run_id}} uses {{run_id}}, but this invocation plans "
        f"{len(runs)} runs. {{run_id}} needs exactly one; "
        "use {invocation_id} instead."
    )
