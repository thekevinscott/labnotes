import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main


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
    with pytest.raises(SystemExit) as exited:
        main(["-c", str(root / ".labnotes.toml"), "experiments", "exp", "run"])
    assert exited.value.code == 0
    records = [json.loads(p.read_text()) for p in root.glob("exp/runs/**/run.json")]
    assert all(record["exit_code"] == 0 for record in records)
    return records


@pytest.mark.parametrize("state", ["clean", "unstaged", "staged", "outside", "unborn"])
def test_records_the_repositories_commit_and_tracked_changes(
    tmp_path: Path, state: str
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text('command = "true"\n')
    expected = None
    if state != "outside":
        git(tmp_path, "init")
        if state != "unborn":
            tracked = tmp_path / "tracked"
            tracked.write_text("original")
            git(tmp_path, "add", "tracked")
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


def test_queued_runs_capture_the_commit_before_their_own_command(
    tmp_path: Path,
) -> None:
    (tmp_path / ".labnotes.toml").write_text("")
    (tmp_path / "exp").mkdir()
    (tmp_path / "exp/experiment.toml").write_text(
        'command = "git -c user.name=Test -c user.email=test@example.com '
        '-c commit.gpgsign=false commit --allow-empty -m next"\nrepeats = 2\n'
    )
    git(tmp_path, "init")
    git(tmp_path, "commit", "--allow-empty", "-m", "initial")

    recorded = run(tmp_path)

    assert len(recorded) == 2
    assert {record["git"]["commit"] for record in recorded} == {
        git(tmp_path, "rev-parse", "HEAD~2"),
        git(tmp_path, "rev-parse", "HEAD~1"),
    }
    assert all(record["git"]["dirty"] is False for record in recorded)
