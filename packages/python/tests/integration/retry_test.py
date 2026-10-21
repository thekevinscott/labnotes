import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from labnotes.cli import main
from labnotes.models import Controls
from labnotes.read_config import read_config
from labnotes.runner.prepare_experiment import prepare_experiment
from labnotes.runner.run_experiment import run_experiment

# Exits with the next code in codes.txt, one per launch, then 0.
SCRIPT = """
import sys
from pathlib import Path

codes = Path("codes.txt")
left = codes.read_text().split()
codes.write_text(" ".join(left[1:]))
sys.exit(int(left[0]) if left else 0)
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(root: Path, codes: str, settings: str = "") -> Path:
    write(root / ".labnotes.toml", "")
    write(root / "script.py", SCRIPT)
    write(root / "codes.txt", codes)
    write(
        root / "exp" / "experiment.toml",
        f'command = "{sys.executable} script.py"\n{settings}[params]\nm = ["a"]\n',
    )
    return root


def runs(root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8")) | {"id": path.parent.name}
        for path in (root / "exp" / "runs").glob("**/run.json")
    ]


def chain(root: Path) -> list[dict[str, Any]]:
    by_parent = {run.get("retry_of"): run for run in runs(root)}
    ordered = [by_parent.pop(None)]
    while ordered[-1]["id"] in by_parent:
        ordered.append(by_parent.pop(ordered[-1]["id"]))
    assert not by_parent
    return ordered


def run_now(root: Path) -> list[dict[str, object]]:
    config = read_config(root / ".labnotes.toml")
    events: list[dict[str, object]] = []

    async def go() -> list[dict[str, object]]:
        experiment, concurrency = await prepare_experiment(config, "exp", None, None)

        def listen(controls: Controls) -> None:
            controls.finish()

        return await run_experiment(
            config,
            "exp",
            experiment,
            concurrency,
            events.append,
            listen,
            retry_seconds=0.01,
        )

    asyncio.run(go())
    return events


def labnotes(root: Path, argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        main(["-c", str(root / ".labnotes.toml"), *argv])
    return exit_info.value.code


def counted(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    capsys.readouterr()
    labnotes(root, ["experiments", "exp", "runs", "--format", "json"])
    return {run["id"]: run["counted"] for run in json.loads(capsys.readouterr().out)}


def test_retries_a_tempfail_into_a_new_folder_that_links_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, "75")

    run_now(root)

    first, second = chain(root)
    assert (first["exit_code"], second["exit_code"]) == (75, 0)
    assert first["params"] == second["params"] == {"m": "a"}
    assert "retry_of" not in first
    assert second["retry_of"] == first["id"]
    assert counted(root, capsys) == {first["id"]: 0, second["id"]: 1}


def test_retries_fill_a_matrix_without_extra_replicates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_project(tmp_path, "75", 'mode = "matrix"\nrepeats = 2\n')

    run_now(root)
    events = run_now(root)

    recorded = runs(root)
    [retry] = [run for run in recorded if "retry_of" in run]
    tempfail = {run["id"]: run["exit_code"] for run in recorded}
    assert sorted(tempfail.values()) == [0, 0, 75]
    assert tempfail[retry["retry_of"]] == 75
    assert sorted(counted(root, capsys).values()) == [0, 1, 1]
    assert [event["event"] for event in events] == ["planned", "idle"]


def test_gives_up_once_the_retries_run_out(tmp_path: Path) -> None:
    root = make_project(tmp_path, "75 75 75 75")

    events = run_now(root)

    recorded = chain(root)
    assert [run["exit_code"] for run in recorded] == [75, 75, 75]
    assert [run.get("retry_of") for run in recorded] == [
        None,
        recorded[0]["id"],
        recorded[1]["id"],
    ]
    assert events[-2:] == [
        {"event": "gave up", "run": recorded[2]["id"], "retries": 2},
        {"event": "idle"},
    ]


@pytest.mark.parametrize(
    ("codes", "settings", "summary"),
    [
        ("1", "", "0 passed, 1 failed.\n"),
        ("75", "retries = 0\n", "0 passed, 1 failed.\n"),
    ],
)
def test_runs_once_without_a_retry_to_make(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    codes: str,
    settings: str,
    summary: str,
) -> None:
    root = make_project(tmp_path, codes, settings)

    assert labnotes(root, ["experiments", "exp", "run"]) == 0

    [only] = runs(root)
    assert only["exit_code"] == int(codes)
    assert capsys.readouterr().out.endswith(summary)
