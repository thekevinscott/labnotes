import json
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

# Exits 1 the first time it runs a value listed in fail.txt, 0 otherwise.
SCRIPT = """
import sys
from pathlib import Path

fail = Path("fail.txt")
listed = fail.read_text().split() if fail.exists() else []
value = sys.argv[sys.argv.index("--m") + 1]
if value in listed:
    listed.remove(value)
    fail.write_text(" ".join(listed))
    sys.exit(1)
"""


def make_project(root: Path, settings: str) -> Path:
    (root / "exp").mkdir(parents=True)
    (root / ".labnotes.toml").write_text("")
    (root / "script.py").write_text(SCRIPT)
    (root / "fail.txt").write_text("a")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\n{settings}'
        '[params]\nm = ["a", "b"]\n'
    )
    return root


def labnotes(
    root: Path, uvx: dict[str, str], *argv: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uvx", "labnotes", "-c", str(root / ".labnotes.toml"), "experiments", *argv],
        cwd=root,
        env={**os.environ, **uvx},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )


def records(root: Path) -> dict[str, dict[str, object]]:
    runs = root / "exp/runs"
    return {
        str(path.parent.relative_to(runs)): json.loads(path.read_text())
        for path in runs.rglob("run.json")
    }


def test_uvx_run_plans_what_failed_then_nothing(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = make_project(tmp_path / "project", "continues = false\n")

    first = labnotes(root, uvx, "exp", "run")
    assert first.stdout.endswith("1 passed, 1 failed.\n"), first.stdout
    second = labnotes(root, uvx, "exp", "run")
    assert second.stdout.endswith("1 passed, 0 failed.\n"), second.stdout
    third = labnotes(root, uvx, "exp", "run")

    assert third.returncode == 0, third.stdout
    assert "Nothing to run" in third.stdout
    recorded = records(root)
    assert len(recorded) == 3
    assert all("/" not in run for run in recorded)


def test_uvx_run_respects_a_held_slot(tmp_path: Path, uvx: dict[str, str]) -> None:
    root = make_project(tmp_path / "project", "continues = false\nrepeats = 1\n")
    held = root / "exp/runs/held"
    held.mkdir(parents=True)
    (held / "run.json").write_text(
        json.dumps(
            {
                "params": {"m": "a"},
                "created": "2026-10-17T00:00:00Z",
                "ended": None,
                "exit_code": None,
                "error": None,
            }
        )
    )
    with (held / "run.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = labnotes(root, uvx, "exp", "run")

    assert result.returncode == 0, result.stdout
    assert "held by another run" in result.stdout
    assert [r["params"] for r in records(root).values()].count({"m": "a"}) == 1


def test_second_uvx_run_does_not_duplicate_an_active_run(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = make_project(tmp_path / "project", "continues = false\nrepeats = 1\n")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\ncontinues = false\n'
        '[params]\nm = ["a"]\n'
    )
    (root / "script.py").write_text("import time\ntime.sleep(6)\n")
    first = subprocess.Popen(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        cwd=root,
        env={**os.environ, **uvx},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not records(root) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert records(root), "first run never started"
        assert first.poll() is None

        second = labnotes(root, uvx, "exp", "run")

        assert second.returncode == 0, second.stdout
        assert "held by another run" in second.stdout
        assert len(records(root)) == 1
    finally:
        first.terminate()
        first.communicate(timeout=15)


def test_uvx_run_continues_a_failed_run_without_a_mode(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = make_project(tmp_path / "project", "continues = true\n")

    labnotes(root, uvx, "exp", "run")
    second = labnotes(root, uvx, "exp", "run")

    assert second.stdout.endswith("1 passed, 0 failed.\n"), second.stdout
    recorded = records(root)
    assert len(recorded) == 2
    [resumed] = [r for r in recorded.values() if r["params"] == {"m": "a"}]
    assert resumed["exit_code"] == 0
    assert len(resumed["invocations"]) == 2  # type: ignore[arg-type]


def test_uvx_run_names_the_migration_for_mode_and_missing_continues(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    with_mode = make_project(tmp_path / "mode", 'continues = false\nmode = "adhoc"\n')
    without_continues = make_project(tmp_path / "continues", "")

    moded = labnotes(with_mode, uvx, "exp", "run")
    bare = labnotes(without_continues, uvx, "exp", "run")

    assert moded.returncode != 0
    assert "mode was removed" in moded.stdout
    assert bare.returncode != 0
    assert "continues = true or continues = false" in bare.stdout
    assert not (with_mode / "exp/runs").exists()
    assert not (without_continues / "exp/runs").exists()


def test_uvx_lists_old_runs_nested_in_group_folders(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    root = make_project(tmp_path / "project", "continues = false\n")
    for name, m in (("a-1a2b", "a"), ("b-3c4d", "b")):
        folder = root / "exp/runs/20261020-065052-still-lake" / name
        folder.mkdir(parents=True)
        (folder / "run.json").write_text(
            json.dumps(
                {"params": {"m": m}, "created": "2026-10-20T06:50:52Z", "exit_code": 0}
            )
        )

    listed = labnotes(root, uvx, "exp", "runs", "--format", "json")

    assert listed.returncode == 0, listed.stdout
    assert sorted(row["id"] for row in json.loads(listed.stdout)) == [
        "20261020-065052-still-lake/a-1a2b",
        "20261020-065052-still-lake/b-3c4d",
    ]
