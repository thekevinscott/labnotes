import asyncio
import json
import sys
from pathlib import Path
import time
from typing import Any

import pytest

from labnotes.cli import main
from labnotes.default_counts import DEFAULT_COUNTS
from labnotes.read_config import read_config
from labnotes.tables.list_experiment_runs import list_experiment_runs
from labnotes.tables.open_tables import open_tables
from conftest import run_tui_command
from curtaincall import Terminal, expect

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


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(root: Path, settings: str = "continues = false\n") -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "script.py", SCRIPT)
    write(
        root / "exp" / "experiment.toml",
        f'command = "{sys.executable} script.py"\nrepeats = 2\n'
        f'{settings}[params]\nm = ["a", "b"]\n',
    )
    return root


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    if len(argv) >= 3 and argv[0] == "experiments" and argv[2] == "run":
        return run_tui_command(root, argv)
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def stored_runs(root: Path, name: str) -> list[dict[str, Any]]:
    async def read() -> list[dict[str, Any]]:
        tables = open_tables(read_config(root / ".labnotes.toml"))
        return await list_experiment_runs(tables, name, DEFAULT_COUNTS)

    return asyncio.run(read())


def run(root: Path) -> None:
    assert labnotes(root, ["experiments", "exp", "run"]) == 0


def runs(root: Path) -> dict[str, dict[str, Any]]:
    folder = root / "exp" / "runs"
    return {
        str(path.parent.relative_to(folder)): json.loads(path.read_text())
        for path in sorted(folder.rglob("run.json"))
    }


def test_plans_nothing_once_every_cell_has_its_repeats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path)
    run(root)
    first = runs(root)
    capsys.readouterr()

    run(root)

    assert runs(root) == first
    assert "0 passed, 0 failed." in capsys.readouterr().out


def test_writes_every_run_to_a_flat_folder(tmp_path: Path) -> None:
    root = make_project(tmp_path)

    run(root)

    recorded = runs(root)
    assert len(recorded) == 4
    assert all("/" not in run_id for run_id in recorded)


def test_plans_failed_runs_again(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    write(root / "fail.txt", "a")
    run(root)
    before = runs(root)

    run(root)

    recorded = runs(root)
    [new] = recorded.keys() - before.keys()
    assert recorded[new]["params"] == {"m": "a"}
    assert recorded[new]["exit_code"] == 0
    assert len(recorded) == 5


def test_continues_a_failed_run_in_its_own_folder(tmp_path: Path) -> None:
    root = make_project(tmp_path, "continues = true\n")
    write(root / "fail.txt", "a")
    run(root)
    [failed] = [run_id for run_id, r in runs(root).items() if r["exit_code"] == 1]

    run(root)

    recorded = runs(root)
    assert len(recorded) == 4
    assert recorded[failed]["exit_code"] == 0
    assert len(recorded[failed]["invocations"]) == 2


@pytest.mark.parametrize("mode", ["adhoc", "matrix"])
def test_rejects_mode_in_experiment_toml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    root = make_project(tmp_path, f'continues = false\nmode = "{mode}"\n')

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    err = capsys.readouterr().err
    assert "mode was removed" in err
    assert "migrations" in err
    assert not (root / "exp" / "runs").exists()


@pytest.mark.parametrize(
    "labnotes_toml",
    ['[experiments]\nmode = "matrix"\n', '[experiment]\nmode = "adhoc"\n'],
)
def test_rejects_mode_in_labnotes_toml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], labnotes_toml: str
) -> None:
    root = make_project(tmp_path)
    write(
        root / ".labnotes.toml",
        '[experiments]\npath = "{experiment}"\n' + labnotes_toml
        if labnotes_toml.startswith("[experiment]")
        else labnotes_toml,
    )

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    assert "mode was removed" in capsys.readouterr().err


def test_requires_continues(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_project(tmp_path, "")

    assert labnotes(root, ["experiments", "exp", "run"]) not in (0, None)

    err = capsys.readouterr().err
    assert "continues = true or continues = false" in err
    assert "migrations" in err
    assert not (root / "exp" / "runs").exists()


def old_nested_run(root: Path, group: str, name: str, m: str) -> None:
    write(
        root / "exp" / "runs" / group / name / "run.json",
        json.dumps(
            {"params": {"m": m}, "created": "2026-10-20T06:50:52Z", "exit_code": 0}
        ),
    )


def test_reads_and_counts_old_runs_nested_in_group_folders(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    for group in ("20261020-065052-still-lake", "20261020-065110-quiet-pond"):
        old_nested_run(root, group, "a-1a2b", "a")
        old_nested_run(root, group, "b-3c4d", "b")

    listed = sorted(str(row["id"]) for row in stored_runs(root, "exp"))

    assert listed == [
        "20261020-065052-still-lake/a-1a2b",
        "20261020-065052-still-lake/b-3c4d",
        "20261020-065110-quiet-pond/a-1a2b",
        "20261020-065110-quiet-pond/b-3c4d",
    ]
    run(root)
    assert len(runs(root)) == 4


# The first launch waits for hold.txt to go; any duplicate exits at once.
HOLD = """
import os
import time
from pathlib import Path

try:
    os.close(os.open("claimed", os.O_CREAT | os.O_EXCL))
except FileExistsError:
    raise SystemExit(0)
while Path("hold.txt").exists():
    time.sleep(0.05)
"""


def test_second_run_sees_the_first_as_held(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path)
    write(root / "script.py", HOLD)
    write(
        root / "exp/experiment.toml",
        f'continues = false\ncommand = "{sys.executable} script.py"\n'
        'repeats = 1\n[params]\nm = ["a"]\n',
    )
    write(root / "hold.txt", "")
    labnotes_bin = Path(sys.executable).parent / "labnotes"
    first = Terminal(
        f"{labnotes_bin} -c {root / '.labnotes.toml'} experiments exp run",
        rows=30,
        cols=120,
    )
    first.start()
    try:
        for _ in range(200):
            if (root / "claimed").exists():
                break
            time.sleep(0.05)
        assert (root / "claimed").exists()
        assert labnotes(root, ["experiments", "exp", "run"]) == 0
        assert len(runs(root)) == 1
    finally:
        (root / "hold.txt").unlink()
        expect(first.get_by_text("1 passed, 0 failed")).to_be_visible(timeout=30)
        first.key_ctrl_c()
        first.wait(timeout=10)
        first.kill()
    assert len(runs(root)) == 1
