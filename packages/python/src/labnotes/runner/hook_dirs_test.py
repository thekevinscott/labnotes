import pytest

from labnotes.runner.hook_dirs import hook_dirs


def test_gives_only_invocation_dir_when_one_run_is_planned() -> None:
    hooks: dict[str, str | None] = {"setup": "up {invocation_dir}", "teardown": None}

    assert hook_dirs(hooks, None, ["/a b/run"]) == {"invocation_dir": "/a b/run"}


def test_gives_adhoc_group_to_multi_run_hooks() -> None:
    hooks: dict[str, str | None] = {"setup": "up {invocation_dir}", "teardown": None}

    assert hook_dirs(hooks, "/a b/group", ["/a b/group/r1", "/a b/group/r2"]) == {
        "invocation_dir": "/a b/group"
    }


@pytest.mark.parametrize("runs", [[], ["/r1"], ["/r1", "/r2"]])
@pytest.mark.parametrize("hook", ["setup", "teardown", "meta"])
def test_rejects_run_dir_in_every_hook(runs: list[str], hook: str) -> None:
    hooks: dict[str, str | None] = {"setup": None, hook: "down {run_dir}"}

    with pytest.raises(ValueError) as error:
        hook_dirs(hooks, "/group", runs)

    assert str(error.value) == (
        f"{hook} command down {{run_dir}} uses {{run_dir}}; "
        "use {invocation_dir} instead."
    )


def test_rejects_invocation_dir_in_multi_run_matrix_hooks() -> None:
    with pytest.raises(ValueError, match=r"setup command .* uses \{invocation_dir\}"):
        hook_dirs({"setup": "up {invocation_dir}"}, None, ["/r1", "/r2"])
