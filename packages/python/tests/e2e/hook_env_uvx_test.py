import json
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_uvx_run_gives_run_dir_env_to_the_run_but_not_to_setup(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(
        '[experiments]\npath = "{experiment}"\n[experiment.env]\nLABEL = "{run_dir}"\n'
    )
    (root / "capture.py").write_text(
        "import json, os, sys\n"
        'print("LABEL", os.environ.get("LABEL"))\n'
        'with open("journal.jsonl", "a") as journal:\n'
        '    journal.write(json.dumps([sys.argv[1], os.environ.get("LABEL")]) + "\\n")\n'
    )
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} capture.py run"\n'
        f'setup = "{sys.executable} capture.py setup"\n'
    )

    term = tui(root, "experiments", "exp", "run", unset=("LABEL",), cols=300)
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    [folder] = (root / "exp/runs").iterdir()
    expect(term.get_by_text(f"LABEL {folder.resolve()}")).to_be_visible()
    tui.quit(term)

    assert [
        json.loads(line) for line in (root / "journal.jsonl").read_text().splitlines()
    ] == [["setup", None], ["run", str(folder.resolve())]]
