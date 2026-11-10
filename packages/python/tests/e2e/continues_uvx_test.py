import json
import subprocess
import sys
from pathlib import Path

from curtaincall import expect

from conftest import Tui

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
print("saved step 20", flush=True)
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


def run(tui: Tui, root: Path, summary: str, *options: str) -> None:
    term = tui(root, "experiments", "exp", "run", *options)
    expect(term.get_by_text(summary)).to_be_visible(timeout=120)
    tui.quit(term)


def records(root: Path) -> dict[Path, dict[str, object]]:
    return {
        path.parent: json.loads(path.read_text())
        for path in root.glob("exp/runs/**/run.json")
    }


def test_uvx_continues_a_failed_run_in_its_own_folder(tmp_path: Path, tui: Tui) -> None:
    root = project(tmp_path / "project", "fail", "continues = true\n")

    run(tui, root, "0 passed, 1 failed.")
    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("resumed from step 20")).to_be_visible()
    tui.quit(term)

    [(folder, record)] = records(root).items()
    assert [i["exit_code"] for i in record["invocations"]] == [1, 0]  # type: ignore[union-attr]
    assert record["exit_code"] == 0
    stdout = [p.read_text() for p in sorted(folder.glob("stdout-*.txt"))]
    assert stdout == ["saved step 20\n", "resumed from step 20\n"]


def test_uvx_continues_a_run_stopped_from_the_tui(tmp_path: Path, tui: Tui) -> None:
    root = project(tmp_path / "project", "hang", "continues = true\n")
    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("saved step 20")).to_be_visible(timeout=120)
    term.key_ctrl_c()
    expect(term.get_by_text("Stop (s)")).to_be_visible()
    term.write("s")
    tui.exited(term)

    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("resumed from step 20")).to_be_visible()
    tui.quit(term)

    [record] = records(root).values()
    first, second = record["invocations"]  # type: ignore[misc]
    assert first["ended_by"] == "stop"
    assert second["exit_code"] == 0


def test_uvx_without_continues_redoes_a_failed_run_in_a_new_folder(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path / "project", "fail", "continues = false\n")

    run(tui, root, "0 passed, 1 failed.")
    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text("0 passed, 1 failed.")).to_be_visible(timeout=120)
    expect(term.get_by_text("resumed")).not_to_be_visible()
    tui.quit(term)

    recorded = records(root)
    assert sorted(r["exit_code"] for r in recorded.values()) == [1, 1]  # type: ignore[type-var]
    for folder, record in recorded.items():
        assert "invocations" not in record
        assert (folder / "stdout.log").exists()


def test_uvx_caps_failed_retries_and_can_replace_the_run(
    tmp_path: Path, tui: Tui
) -> None:
    root = project(tmp_path / "project", "fail", "continues = true\nretries = 2\n")
    (root / "script.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        'p = Path(os.environ["LABNOTES_RUN"]) / "attempts"\n'
        'p.write_text(p.read_text() + "x" if p.exists() else "x")\n'
        "sys.exit(1)\n"
    )
    for _ in range(3):
        run(tui, root, "0 passed, 1 failed.")
    [(folder, record)] = records(root).items()
    before = (folder / "run.json").read_bytes()

    run(tui, root, "0 passed, 0 failed.")
    assert records(root) == {folder: record}
    assert (folder / "run.json").read_bytes() == before
    assert (folder / "attempts").read_text() == "xxx"

    run(tui, root, "0 passed, 1 failed.", "--replace-capped")
    assert len(records(root)) == 2
    assert (folder / "run.json").read_bytes() == before


def test_uvx_resume_honors_repeated_param_values(tmp_path: Path, tui: Tui) -> None:
    root = project(tmp_path / "project", "fail", "")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} -c pass"\ncontinues = true\n[params]\nm = [1, 1, 2]\n'
    )
    done = root / "exp/runs/done"
    done.mkdir(parents=True)
    (done / "run.json").write_text(
        json.dumps(
            {
                "params": {"m": 1},
                "created": "2026-10-17T00:00:00Z",
                "ended": "2026-10-17T01:00:00Z",
                "exit_code": 0,
                "error": None,
            }
        )
    )

    run(tui, root, "2 passed, 0 failed.")

    found = sorted(r["params"]["m"] for r in records(root).values())  # type: ignore[index]
    assert found == [1, 1, 2]


def test_uvx_keeps_each_invocations_commit_and_patch(tmp_path: Path, tui: Tui) -> None:
    root = project(tmp_path / "project", "fail", "continues = true\n")
    (root / ".gitignore").write_text("exp/runs/\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@t", "commit", "-qm", "i"],
        cwd=root,
        check=True,
    )

    (root / "notes.txt").write_text("first\n")
    run(tui, root, "0 passed, 1 failed.")
    (root / "notes.txt").unlink()
    (root / "other.txt").write_text("second\n")
    run(tui, root, "1 passed, 0 failed.")

    [(folder, record)] = records(root).items()
    first, second = record["invocations"]  # type: ignore[misc]
    assert (first["dirty"], second["dirty"]) == (True, True)
    assert "notes.txt" in (folder / first["patch"]).read_text()
    assert "other.txt" in (folder / second["patch"]).read_text()
    assert "notes.txt" not in (folder / second["patch"]).read_text()
