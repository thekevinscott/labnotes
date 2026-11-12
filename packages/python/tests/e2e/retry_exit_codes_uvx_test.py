import json
import sys
from pathlib import Path

import pytest
from curtaincall import expect

from conftest import Tui

# Exits with the next code in codes.txt, one per launch, then 0.
SCRIPT = """
import sys
from pathlib import Path

codes = Path("codes.txt")
left = codes.read_text().split()
codes.write_text(" ".join(left[1:]))
sys.exit(int(left[0]) if left else 0)
"""


def make_project(root: Path, codes: str, project: str, experiment: str) -> None:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(project)
    (root / "script.py").write_text(SCRIPT)
    (root / "codes.txt").write_text(codes)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} script.py"\n'
        f"retry_wait = 0\n{experiment}"
    )


def exit_codes(root: Path) -> list[int]:
    recorded = [
        json.loads(path.read_text()) for path in root.glob("exp/runs/**/run.json")
    ]
    return sorted(run["exit_code"] for run in recorded)


@pytest.mark.parametrize(
    ("project", "experiment", "flags"),
    [
        ("", "retry_exit_codes = [1]\n", []),
        ("[experiments]\nretry_exit_codes = [1]\n", "", []),
        ("", "retry_exit_codes = [2]\n", ["--retry-exit-code", "1"]),
    ],
)
def test_uvx_retries_a_listed_exit_code(
    tmp_path: Path,
    tui: Tui,
    project: str,
    experiment: str,
    flags: list[str],
) -> None:
    root = tmp_path / "project"
    make_project(root, "1", project, experiment)

    term = tui(root, "experiments", "exp", "run", *flags)

    expect(term.get_by_text("1 passed, 0 failed. 1 retried.")).to_be_visible(
        timeout=120
    )
    tui.quit(term)
    assert exit_codes(root) == [0, 1]


def test_uvx_does_not_retry_an_unlisted_exit_code(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    make_project(root, "75", "", "retry_exit_codes = [1]\n")

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
    assert exit_codes(root) == [75]


def test_uvx_gives_up_naming_the_exit_code(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    make_project(root, "1 1", "", "retries = 1\nretry_exit_codes = [1]\n")

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("gave up (exit 1)")).to_be_visible(timeout=120)
    tui.quit(term)
    assert exit_codes(root) == [1, 1]
