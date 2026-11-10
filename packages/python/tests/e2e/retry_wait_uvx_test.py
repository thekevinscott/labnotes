import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from curtaincall import expect

from conftest import Tui

# Exits 75 on the first launch, then 0.
SCRIPT = """
import sys
from pathlib import Path

first = Path("launched")
if first.exists():
    sys.exit(0)
first.touch()
sys.exit(75)
"""


def seconds(stamp: str) -> float:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").timestamp()


@pytest.mark.parametrize(
    ("project", "experiment", "flags"),
    [
        ("[experiments]\nretry_wait = 1\n", "", []),
        (
            "[experiments]\nretry_wait = 60\n",
            "retry_wait = 60\n",
            ["--retry-wait", "1"],
        ),
    ],
)
def test_uvx_a_short_retry_wait_retries_sooner(
    tmp_path: Path,
    tui: Tui,
    project: str,
    experiment: str,
    flags: list[str],
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text(project)
    (root / "script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "{sys.executable} script.py"\n{experiment}'
    )

    term = tui(root, "experiments", "exp", "run", *flags)

    expect(term.get_by_text("1 passed, 0 failed. 1 retried.")).to_be_visible(
        timeout=120
    )
    tui.quit(term)
    recorded = [
        json.loads(path.read_text()) for path in root.glob("exp/runs/**/run.json")
    ]
    [first] = [run for run in recorded if "retry_of" not in run]
    [retry] = [run for run in recorded if "retry_of" in run]
    gap = seconds(str(retry["created"])) - seconds(str(first["ended"]))
    assert 1 <= gap < 10
