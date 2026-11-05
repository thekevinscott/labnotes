from conftest import run_uvx_tui
import json
import subprocess
import sys
from pathlib import Path


def run(
    root: Path, uvx: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return run_uvx_tui(root, uvx, "experiments", "exp", "run", *args)


def test_uvx_restarts_only_the_selected_failed_run(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = tmp_path / "project"
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "m = sys.argv[sys.argv.index('--m') + 1]\n"
        "with Path('launches.txt').open('a') as log: log.write(m + '\\n')\n"
        "if m == 'a' and Path('fail-once').exists():\n"
        "    Path('fail-once').unlink()\n    sys.exit(1)\n"
    )
    (root / "fail-once").write_text("")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n'
        'continues = false\nretries = 0\n[params]\nm = ["a", "b"]\n'
    )

    first = run(root, uvx)
    assert first.returncode == 0, first.stdout + first.stderr
    before = {
        path.parent.name: json.loads(path.read_text())
        for path in (root / "exp/runs").rglob("run.json")
    }
    [failed_id] = [
        run_id for run_id, record in before.items() if record["exit_code"] == 1
    ]

    second = run(root, uvx, "--run-id", failed_id)

    assert second.returncode == 0, second.stdout + second.stderr
    assert (root / "launches.txt").read_text().splitlines() == ["a", "b", "a"]
    assert len(list((root / "exp/runs").rglob("run.json"))) == 3
