from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_rejects_an_env_key_that_is_not_a_shell_identifier(
    tmp_path: Path, tui: Tui
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        'command = "true"\ncontinues = false\n[env]\n"with-dash" = "x"\n'
    )

    term = tui(tmp_path, "experiments", "exp", "run")

    assert tui.exited(term) != 0, term.to_snapshot()
    expect(term.get_by_text("env.with-dash must be a")).to_be_visible()
    assert not list(tmp_path.glob("exp/runs/*/run.json"))
