import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from conftest import run_tui_command


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=root,
        text=True,
    ).strip()


def run(root: Path) -> list[dict[str, Any]]:
    assert run_tui_command(root, ["experiments", "exp", "run"]) == 0
    records = [json.loads(p.read_text()) for p in root.glob("exp/runs/**/run.json")]
    assert all(record["exit_code"] == 0 for record in records)
    return records


@pytest.mark.parametrize("state", ["clean", "unstaged", "staged", "outside", "unborn"])
def test_records_the_repositories_commit_and_tracked_changes(
    tmp_path: Path, state: str
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "true"\n'
    )
    expected = None
    if state != "outside":
        git(tmp_path, "init")
        if state != "unborn":
            tracked = tmp_path / "tracked"
            tracked.write_text("original")
            git(tmp_path, "add", ".")
            git(tmp_path, "commit", "-m", "initial")
            if state != "clean":
                tracked.write_text("changed")
            if state == "staged":
                git(tmp_path, "add", "tracked")
            expected = {
                "commit": git(tmp_path, "rev-parse", "HEAD"),
                "dirty": state != "clean",
            }

    [record] = run(tmp_path)

    assert record["git"] == expected


def test_queued_runs_keep_the_invocations_starting_commit(
    tmp_path: Path,
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        f'continues = false\ncommand = "git -C {tmp_path} -c user.name=Test -c user.email=test@example.com '
        '-c commit.gpgsign=false commit --allow-empty -m next"\nrepeats = 2\n'
    )
    git(tmp_path, "init")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")

    recorded = run(tmp_path)

    assert len(recorded) == 2
    assert {record["git"]["commit"] for record in recorded} == {
        git(tmp_path, "rev-parse", "HEAD~2")
    }
    assert all(record["git"]["dirty"] is False for record in recorded)


def test_untracked_files_make_the_run_dirty_and_land_in_its_patch(
    tmp_path: Path,
) -> None:
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        'continues = false\ncommand = "true"\n'
    )
    git(tmp_path, "init")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    (tmp_path / "helper.py").write_text("print('new')\n")
    (tmp_path / "weights.bin").write_bytes(b"\0\1\2")
    (tmp_path / "ignored.txt").write_text("secret\n")

    [record] = run(tmp_path)

    assert record["git"]["dirty"] is True
    [patch] = tmp_path.glob("exp/runs/**/git-diff.patch")
    text = patch.read_text()
    assert "+++ b/helper.py\n@@ -0,0 +1 @@\n+print('new')\n" in text
    assert "Binary files /dev/null and b/weights.bin differ" in text
    assert "ignored.txt" not in text
