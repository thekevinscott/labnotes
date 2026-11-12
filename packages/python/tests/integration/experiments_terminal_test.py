import json
import sys
from pathlib import Path

import pytest
from curtaincall import expect


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def project(root: Path) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "alpha/experiment.toml", 'continues = false\ncommand = "go"\n')
    write(
        root / "alpha/runs/20261017-000000/first/run.json",
        json.dumps({"created": "2026-10-17T00:00:00Z", "exit_code": 0}),
    )
    write(root / "beta/files/notes.md", "notes")
    return root


@pytest.mark.parametrize(
    ("argv", "shown"),
    [
        ("", ["display_name", "alpha", "beta"]),
        ("alpha", ["last_run", "alpha", "2026-10-17T00:00:00Z"]),
    ],
)
def test_prints_the_table_and_exits_in_a_terminal(
    terminal, tmp_path: Path, argv: str, shown: list[str]
) -> None:
    root = project(tmp_path)
    command = Path(sys.executable).parent / "labnotes"
    term = terminal(
        f"{command} -c {root / '.labnotes.toml'} experiments {argv}",
        rows=30,
        cols=300,
    )

    expect(term).to_have_exited(timeout=30)
    for text in shown:
        assert term.get_by_text(text).is_visible(), term.to_snapshot()
    assert term.exit_code == 0, term.to_snapshot()
