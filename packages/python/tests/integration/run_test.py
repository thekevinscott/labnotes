import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main

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


@pytest.fixture
def project(tmp_path: Path) -> Path:
    write(tmp_path / ".labnotes.toml", "")
    write(tmp_path / "script.py", SCRIPT)
    write(
        tmp_path / "exp" / "experiment.toml",
        f'command = "{sys.executable} script.py --out {{run_dir}}"\n'
        'repeats = 2\nmode = "fill"\n[params]\nm = ["a", "b"]\n',
    )
    return tmp_path


def labnotes(project: Path, argv: list[str]) -> int | str | None:
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
    assert labnotes(project, ["experiments", "exp", "run", "--concurrency", "2"]) == 1

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


def test_reruns_every_combination_without_a_mode(project: Path) -> None:
    toml = project / "exp" / "experiment.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace('mode = "fill"\n', ""))
    labnotes(project, ["experiments", "exp", "run"])
    labnotes(project, ["experiments", "exp", "run"])

    recorded = runs(project)
    assert sorted(run["params"]["m"] for run in recorded) == ["a"] * 4 + ["b"] * 4
    groups = [run["folder"].parent for run in recorded]
    assert sorted(groups.count(group) for group in set(groups)) == [4, 4]


def test_fills_by_the_project_mode(project: Path) -> None:
    toml = project / "exp" / "experiment.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace('mode = "fill"\n', ""))
    (project / ".labnotes.toml").write_text('[experiments]\nmode = "fill"\n')
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


def test_names_adhoc_runs_by_the_params_that_vary(project: Path) -> None:
    write(
        project / "exp" / "experiment.toml",
        f'command = "{sys.executable} script.py --out {{run_dir}}"\n'
        'mode = "adhoc"\n[params]\nm = ["data/x 1", "data/y"]\nk = ["same"]\n',
    )
    labnotes(project, ["experiments", "exp", "run"])

    names = sorted(run["folder"].name for run in runs(project))
    assert [name[:-5] for name in names] == ["x-1", "y"]
    assert all(re.fullmatch(r"[a-z0-9-]+-[0-9a-f]{4}", name) for name in names)
