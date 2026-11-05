import json
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import pytest

from labnotes.cli import main
from curtaincall import Terminal
from conftest import run_tui_command

SCRIPT = """
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args.pop(args.index("--out") + 1))
args.remove("--out")
(out / "out.txt").write_text(" ".join(args))
Path("cwd.txt").write_text("root")
print("ran", *args)
sys.exit(1 if "b" in args else 0)
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(root: Path) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "script.py", SCRIPT)
    write(
        root / "exp" / "experiment.toml",
        f'continues = false\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n'
        'repeats = 2\n[params]\nm = ["a", "b"]\n',
    )
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return make_project(tmp_path)


def labnotes(project: Path, argv: list[str]) -> int | str | None:
    if argv[:3] == ["experiments", "exp", "run"]:
        return run_tui_command(project, argv)
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(project / ".labnotes.toml"), *argv])
    return exit_info.value.code


def runs(project: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8")) | {"folder": path.parent}
        for path in sorted((project / "exp" / "runs").glob("**/run.json"))
    ]


def test_runs_every_param_combination_repeats_times(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert labnotes(project, ["experiments", "exp", "run", "--concurrency", "2"]) == 0

    recorded = runs(project)
    assert sorted(run["params"]["m"] for run in recorded) == ["a", "a", "b", "b"]
    for run in recorded:
        m = run["params"]["m"]
        assert run["exit_code"] == (1 if m == "b" else 0)
        assert run["created"] <= run["ended"]
        assert (run["folder"] / "out.txt").read_text() == f"--m {m}"
        assert (run["folder"] / "stdout.log").read_text() == f"ran --m {m}\n"
    assert (project / "cwd.txt").read_text() == "root"
    assert capsys.readouterr().out.endswith("2 passed, 2 failed.\n")


def test_reruns_only_the_runs_that_failed(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labnotes(project, ["experiments", "exp", "run"])
    labnotes(project, ["experiments", "exp", "run"])

    recorded = runs(project)
    assert sorted(run["params"]["m"] for run in recorded) == ["a", "a"] + ["b"] * 4


def test_reruns_an_excluded_run(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labnotes(project, ["experiments", "exp", "run"])
    [excluded, _] = [run for run in runs(project) if run["params"]["m"] == "a"]
    run_json = excluded["folder"] / "run.json"
    recorded = json.loads(run_json.read_text(encoding="utf-8"))
    run_json.write_text(json.dumps(recorded | {"excluded": True}))
    labnotes(project, ["experiments", "exp", "run"])
    capsys.readouterr()

    labnotes(project, ["experiments", "exp", "runs", "--format", "json"])

    listed = json.loads(capsys.readouterr().out)
    a_runs = [run for run in listed if json.loads(run["params"]) == {"m": "a"}]
    assert sorted(run["counted"] for run in a_runs) == [0, 1, 1]


def test_counts_runs_by_the_experiments_rule(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    toml = project / "exp" / "experiment.toml"
    toml.write_text('counts = "true"\n' + toml.read_text(encoding="utf-8"))
    labnotes(project, ["experiments", "exp", "run"])
    capsys.readouterr()

    labnotes(project, ["experiments", "exp", "run"])

    assert len(runs(project)) == 4
    assert capsys.readouterr().out.endswith("0 passed, 0 failed.\n")


STAMP = r"\d{8}-\d{6}-[a-z]+-[a-z]+(-\d+)?"


def run_params(project: Path, params: str) -> list[dict[str, Any]]:
    write(
        project / "exp" / "experiment.toml",
        f'continues = false\ncommand = "{sys.executable} script.py --out {{run_dir}}"\n'
        f"[params]\n{params}",
    )
    labnotes(project, ["experiments", "exp", "run"])
    return runs(project)


def test_keeps_the_real_param_values_in_run_json(project: Path) -> None:
    recorded = run_params(project, 'm = ["data/x 1", "data/y"]\n')

    assert sorted(run["params"]["m"] for run in recorded) == ["data/x 1", "data/y"]
    for run in recorded:
        assert (run["folder"] / "out.txt").read_text() == f"--m {run['params']['m']}"


def test_records_the_command_each_run_executed(project: Path) -> None:
    recorded = run_params(project, 'm = ["data/x 1", "data/y"]\n')

    for run in recorded:
        folder = shlex.quote(str(run["folder"]))
        m = shlex.quote(run["params"]["m"])
        assert run["command"] == f"{sys.executable} script.py --out {folder} --m {m}"


def test_names_every_run_with_a_stamp_directly_under_runs(project: Path) -> None:
    labnotes(project, ["experiments", "exp", "run"])

    for run in runs(project):
        assert run["folder"].parent == project / "exp" / "runs"
        assert re.fullmatch(STAMP, run["folder"].name)


def test_runs_in_a_project_whose_path_is_too_long_for_a_socket(project: Path) -> None:
    assert len(str(project)) > 120

    assert labnotes(project, ["experiments", "exp", "run"]) == 0

    assert len(runs(project)) == 4


SLEEPER = """
import os
import signal
import sys
import time
from pathlib import Path

args = sys.argv[1:]
if "--stubborn" in args:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path("pid.txt").write_text(str(os.getpid()))
if "--die" in args:
    os.kill(os.getpid(), signal.SIGKILL)
Path(f"started-{os.getpid()}.txt").write_text("")
time.sleep(float(args[args.index("--s") + 1]))
"""


def sleeper(
    root: Path, seconds: list[float], stubborn: bool = False, die: bool = False
) -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "sleep.py", SLEEPER)
    flag = (" --stubborn" if stubborn else "") + (" --die" if die else "")
    write(
        root / "exp" / "experiment.toml",
        f'continues = false\ncommand = "{sys.executable} sleep.py{flag}"\n'
        f"[params]\ns = {json.dumps(seconds)}\n",
    )
    return root


def test_stops_only_the_runs_that_outlast_the_timeout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = sleeper(tmp_path, [0.1, 30])

    argv = ["experiments", "exp", "run", "--concurrency", "2", "--timeout", "2"]
    assert labnotes(project, argv) == 0

    recorded = {run["params"]["s"]: run for run in runs(project)}
    assert (recorded[0.1]["exit_code"], recorded[0.1]["error"]) == (0, None)
    assert (recorded[0.1]["ended_by"], recorded[0.1]["signal"]) == (None, None)
    assert recorded[30]["exit_code"] != 0
    assert recorded[30]["error"] == "timed out after 2s"
    assert (recorded[30]["ended_by"], recorded[30]["signal"]) == ("timeout", 15)
    assert "timed out after 2s" in capsys.readouterr().out


def test_kills_a_timed_out_run_that_ignores_sigterm(tmp_path: Path) -> None:
    project = sleeper(tmp_path, [30], stubborn=True)

    assert labnotes(project, ["experiments", "exp", "run", "--timeout", "1"]) == 0

    [run] = runs(project)
    assert run["error"] == "timed out after 1s"
    assert run["ended_by"] == "timeout"
    # The shell around the script can die on SIGTERM before SIGKILL lands.
    assert run["signal"] in (signal.SIGTERM, signal.SIGKILL)
    stubborn = int((project / "pid.txt").read_text())
    assert not psutil.pid_exists(stubborn)


def test_records_a_signal_labnotes_did_not_send(tmp_path: Path) -> None:
    project = sleeper(tmp_path, [30], die=True)

    labnotes(project, ["experiments", "exp", "run"])

    [run] = runs(project)
    assert (run["ended_by"], run["signal"], run["error"]) == ("signal", 9, None)


def test_records_runs_stopped_by_stopping_labnotes(tmp_path: Path) -> None:
    project = sleeper(tmp_path, [30])
    command = Path(sys.executable).parent / "labnotes"
    config = project / ".labnotes.toml"
    term = Terminal(f"{command} -c {config} experiments exp run", rows=30, cols=120)
    term.start()
    try:
        for _ in range(100):
            if any(project.glob("started-*.txt")):
                break
            time.sleep(0.1)
        assert any(project.glob("started-*.txt"))
        result = subprocess.run(
            [command, "-c", config, "experiments", "exp", "stop"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        for _ in range(100):
            if runs(project) and runs(project)[0].get("ended"):
                break
            time.sleep(0.1)
    finally:
        term.kill()

    [run] = runs(project)
    assert (run["ended_by"], run["signal"], run["error"]) == ("stop", 15, None)
