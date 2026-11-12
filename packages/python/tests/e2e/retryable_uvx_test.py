import json
import sys
from pathlib import Path

import pytest
from curtaincall import expect

from conftest import Tui

# Exits with the next code in codes.txt, saying why on stderr, then 0.
SCRIPT = """
import sys
from pathlib import Path

codes = Path("codes.txt")
left = codes.read_text().splitlines()
codes.write_text("\\n".join(left[1:]))
if left:
    code, reason = left[0].split(" ", 1)
    print(f"error: {reason}", file=sys.stderr)
    sys.exit(int(code))
"""
# Retries only an attempt whose stderr says the SSH connection timed out.
RETRYABLE = """
import json
import sys
from pathlib import Path

attempt = json.load(sys.stdin)
sys.exit(0 if "timed out" in Path(attempt["stderr"]).read_text() else 1)
"""
CHECK = f'retryable = "{sys.executable} retryable.py"\n'


def make_project(root: Path, codes: list[str], project: str, experiment: str) -> None:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(project)
    (root / "script.py").write_text(SCRIPT)
    (root / "codes.txt").write_text("\n".join(codes))
    (root / "exp/retryable.py").write_text(RETRYABLE)
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
    ("project", "experiment"),
    [("", CHECK), ("[experiments]\n" + CHECK, "")],
)
def test_uvx_retries_a_failure_the_check_approves(
    tmp_path: Path, tui: Tui, project: str, experiment: str
) -> None:
    root = tmp_path / "project"
    make_project(root, ["1 ssh timed out"], project, experiment)

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("1 passed, 0 failed. 1 retried.")).to_be_visible(
        timeout=120
    )
    tui.quit(term)
    assert exit_codes(root) == [0, 1]


def test_uvx_does_not_retry_a_failure_the_check_rejects(
    tmp_path: Path, tui: Tui
) -> None:
    root = tmp_path / "project"
    make_project(root, ["1 bug in the code"], "", CHECK)

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    tui.quit(term)
    assert exit_codes(root) == [1]


def test_uvx_gives_up_naming_the_exit_code(tmp_path: Path, tui: Tui) -> None:
    root = tmp_path / "project"
    codes = ["1 ssh timed out", "1 ssh timed out"]
    make_project(root, codes, "", "retries = 1\n" + CHECK)

    term = tui(root, "experiments", "exp", "run")

    expect(term.get_by_text("0 passed, 1 failed. 1 retried.")).to_be_visible(
        timeout=120
    )
    term.key_escape()
    expect(term.get_by_text("gave up (exit 1)")).to_be_visible()
    tui.quit(term)
    assert exit_codes(root) == [1, 1]
