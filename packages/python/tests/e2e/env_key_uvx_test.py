import os
from pathlib import Path

from curtaincall import expect


def test_uvx_run_rejects_an_env_key_that_is_not_a_shell_identifier(
    terminal, tmp_path: Path, uvx: dict[str, str]
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        'command = "true"\ncontinues = false\n[env]\n"with-dash" = "x"\n'
    )

    term = terminal(
        f"uvx labnotes -c {tmp_path / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
        env={**os.environ, **uvx},
    )

    expect(term.get_by_text("env.with-dash must be a")).to_be_visible(timeout=60)
    term.wait()
    assert term.exit_code != 0
    assert not list(tmp_path.glob("exp/runs/*/run.json"))
