from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_rejects_an_escaping_runs_path_before_writing(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "alpha").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(
        '[runs]\npath = "../escaped-{experiment}/{run}"\n'
    )
    (root / "alpha/experiment.toml").write_text(
        'command = "python3 -c pass"\ncontinues = false\n'
    )

    term = tui(root, "experiments", "alpha", "run")

    assert tui.exited(term) != 0, term.to_snapshot()
    expect(term.get_by_text("[runs] path must be relative")).to_be_visible()
    assert not (tmp_path / "escaped-alpha").exists()
