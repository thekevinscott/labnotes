from conftest import run_uvx_tui
from curtaincall import Terminal
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

# The first launch in a run folder leaves a checkpoint, then fails or hangs;
# a later launch finds the checkpoint and finishes.
SCRIPT = """
import os
import sys
import time
from pathlib import Path

folder = Path(os.environ["LABNOTES_RUN"])
checkpoint = folder / "checkpoint.txt"
if checkpoint.exists():
    print("resumed from", checkpoint.read_text())
    sys.exit(0)
checkpoint.write_text("step 20")
if sys.argv[1] == "hang":
    time.sleep(600)
sys.exit(1)
"""


def project(root: Path, first: str, settings: str) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py {first}"\n'
        f'{settings}[params]\nm = ["a"]\n'
    )
    return root


def labnotes(root: Path) -> list[str]:
    config = str(root / ".labnotes.toml")
    return ["uvx", "labnotes", "-c", config, "experiments", "exp", "run"]


def run(root: Path, uvx: dict[str, str], *options: str) -> str:
    result = run_uvx_tui(root, uvx, "experiments", "exp", "run", *options)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def records(root: Path) -> dict[Path, dict[str, object]]:
    return {
        path.parent: json.loads(path.read_text())
        for path in root.glob("exp/runs/**/run.json")
    }


def test_uvx_continues_a_failed_run_in_its_own_folder(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(tmp_path / "project", "fail", "continues = true\n")

    run(root, uvx)
    output = run(root, uvx)

    assert output.endswith("1 passed, 0 failed.\n"), output
    [(folder, record)] = records(root).items()
    assert [i["exit_code"] for i in record["invocations"]] == [1, 0]  # type: ignore[union-attr]
    assert record["exit_code"] == 0
    stdout = [p.read_text() for p in sorted(folder.glob("stdout-*.txt"))]
    assert stdout == ["", "resumed from step 20\n"]


def test_uvx_continues_a_run_killed_with_labnotes(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(tmp_path / "project", "hang", "continues = true\n")
    term = Terminal(
        shlex.join(labnotes(root)), rows=30, cols=120, env={**os.environ, **uvx}
    )
    term.start()
    try:
        for _ in range(600):
            if list(root.glob("exp/runs/*/checkpoint.txt")):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("run did not start")
        term.kill()
        stopped = subprocess.run(
            [
                "uvx",
                "labnotes",
                "-c",
                str(root / ".labnotes.toml"),
                "experiments",
                "exp",
                "stop",
            ],
            cwd=root,
            env={**os.environ, **uvx},
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert stopped.returncode == 0, stopped.stderr
        for _ in range(300):
            [record] = records(root).values()
            if record.get("ended"):
                break
            time.sleep(0.05)
        run(root, uvx)
    finally:
        term.kill()

    [record] = records(root).values()
    first, second = record["invocations"]  # type: ignore[misc]
    assert first["ended_by"] == "stop"
    assert second["exit_code"] == 0


def test_uvx_without_continues_redoes_a_failed_run_in_a_new_folder(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(tmp_path / "project", "fail", "continues = false\n")

    run(root, uvx)
    run(root, uvx)

    recorded = records(root)
    assert sorted(r["exit_code"] for r in recorded.values()) == [1, 1]  # type: ignore[type-var]
    for folder, record in recorded.items():
        assert "invocations" not in record
        assert (folder / "stdout.log").exists()


def test_uvx_caps_failed_retries_and_can_replace_the_run(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = project(tmp_path / "project", "fail", "continues = true\nretries = 2\n")
    (root / "script.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        'p = Path(os.environ["LABNOTES_RUN"]) / "attempts"\n'
        'p.write_text(p.read_text() + "x" if p.exists() else "x")\n'
        "sys.exit(1)\n"
    )
    for _ in range(3):
        run(root, uvx)
    [(folder, record)] = records(root).items()
    before = (folder / "run.json").read_bytes()

    output = run(root, uvx)
    assert "0 passed, 0 failed." in output
    assert records(root) == {folder: record}
    assert (folder / "run.json").read_bytes() == before
    assert (folder / "attempts").read_text() == "xxx"

    run(root, uvx, "--replace-capped")
    assert len(records(root)) == 2
    assert (folder / "run.json").read_bytes() == before
