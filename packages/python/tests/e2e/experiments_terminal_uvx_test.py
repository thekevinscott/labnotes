import json
from pathlib import Path

import pytest

from conftest import Tui


@pytest.mark.parametrize(
    ("argv", "shown"),
    [
        ((), ["display_name", "alpha", "beta"]),
        (("alpha",), ["last_run", "alpha", "2026-10-17T00:00:00Z"]),
    ],
)
def test_uvx_labnotes_prints_the_table_and_exits_in_a_terminal(
    tmp_path: Path, tui: Tui, argv: tuple[str, ...], shown: list[str]
) -> None:
    root = tmp_path / "project"
    run = root / "alpha/runs/20261017-000000/first"
    run.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0})
    )
    (root / "alpha/experiment.toml").write_text('continues = false\ncommand = "go"\n')
    (root / "beta/files").mkdir(parents=True)
    (root / "beta/files/notes.md").write_text("notes")
    (root / ".labnotes.toml").write_text("")

    term = tui(root, "experiments", *argv, cols=300)

    assert tui.exited(term) == 0, term.to_snapshot()
    for text in shown:
        assert term.get_by_text(text).is_visible(), term.to_snapshot()
