import fcntl
import json
import sys
from pathlib import Path

from curtaincall import Terminal, expect

from conftest import Tui

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


def run(tui: Tui, root: Path, summary: str) -> None:
    term = tui(root, "experiments", "exp", "run")
    expect(term.get_by_text(summary)).to_be_visible(timeout=120)
    tui.quit(term)


def refused(tui: Tui, root: Path) -> Terminal:
    term = tui(root, "experiments", "exp", "run")
    assert tui.exited(term) != 0, term.to_snapshot()
    return term


def records(root: Path) -> dict[str, dict[str, object]]:
    runs = root / "exp/runs"
    return {
        str(path.parent.relative_to(runs)): json.loads(path.read_text())
        for path in runs.rglob("run.json")
    }


def test_uvx_run_plans_what_failed_then_nothing(tmp_path: Path, tui: Tui) -> None:
    root = make_project(tmp_path / "project", "continues = false\n")

    run(tui, root, "1 passed, 1 failed.")
    run(tui, root, "1 passed, 0 failed.")
    run(tui, root, "0 passed, 0 failed.")

    recorded = records(root)
    assert len(recorded) == 3
    assert all("/" not in run for run in recorded)


def test_uvx_run_respects_a_held_slot(tmp_path: Path, tui: Tui) -> None:
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
        run(tui, root, "1 passed, 0 failed.")

    assert [r["params"] for r in records(root).values()].count({"m": "a"}) == 1


def test_second_uvx_run_does_not_duplicate_an_active_run(
    tmp_path: Path, tui: Tui
) -> None:
    root = make_project(tmp_path / "project", "continues = false\nrepeats = 1\n")
    (root / "exp/experiment.toml").write_text(
        f'command = "{sys.executable} script.py"\ncontinues = false\n'
        '[params]\nm = ["a"]\n'
    )
    (root / "script.py").write_text(
        "import time\nprint('working', flush=True)\ntime.sleep(6)\n"
    )
    first = tui(root, "experiments", "exp", "run")
    expect(first.get_by_text("working")).to_be_visible(timeout=120)

    run(tui, root, "0 passed, 0 failed.")

    expect(first.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=15)
    tui.quit(first)
    assert len(records(root)) == 1


def test_uvx_run_continues_a_failed_run_without_a_mode(
    tmp_path: Path, tui: Tui
) -> None:
    root = make_project(tmp_path / "project", "continues = true\n")

    run(tui, root, "1 passed, 1 failed.")
    run(tui, root, "1 passed, 0 failed.")

    recorded = records(root)
    assert len(recorded) == 2
    [resumed] = [r for r in recorded.values() if r["params"] == {"m": "a"}]
    assert resumed["exit_code"] == 0
    assert len(resumed["invocations"]) == 2  # type: ignore[arg-type]


def test_uvx_run_names_the_migration_for_mode_and_missing_continues(
    tmp_path: Path, tui: Tui
) -> None:
    with_mode = make_project(tmp_path / "mode", 'continues = false\nmode = "adhoc"\n')
    without_continues = make_project(tmp_path / "continues", "")

    moded = refused(tui, with_mode)
    bare = refused(tui, without_continues)

    expect(moded.get_by_text("mode was removed")).to_be_visible()
    expect(bare.get_by_text("continues = true or continues = false")).to_be_visible()
    assert not (with_mode / "exp/runs").exists()
    assert not (without_continues / "exp/runs").exists()


def test_uvx_counts_old_runs_nested_in_group_folders(tmp_path: Path, tui: Tui) -> None:
    root = make_project(tmp_path / "project", "continues = false\n")
    for name, m in (("a-1a2b", "a"), ("b-3c4d", "b")):
        folder = root / "exp/runs/20261020-065052-still-lake" / name
        folder.mkdir(parents=True)
        (folder / "run.json").write_text(
            json.dumps(
                {"params": {"m": m}, "created": "2026-10-20T06:50:52Z", "exit_code": 0}
            )
        )

    run(tui, root, "0 passed, 0 failed.")

    assert sorted(records(root)) == [
        "20261020-065052-still-lake/a-1a2b",
        "20261020-065052-still-lake/b-3c4d",
    ]
