import json
from pathlib import Path

from labnotes.tables.read_run import read_run


def write_run(path: Path, run: object) -> str:
    path.mkdir(parents=True)
    (path / "run.json").write_text(json.dumps(run), encoding="utf-8")
    return str(path / "run.json")


def test_reads_a_run_row(tmp_path: Path) -> None:
    run = {
        "params": {"model": "opus", "effort": "low"},
        "created": "2026-10-17T00:00:00Z",
        "ended": "2026-10-17T00:01:00Z",
        "exit_code": 0,
        "error": None,
        "excluded": True,
    }
    path = write_run(tmp_path / "exp" / "runs" / "brave-fox", run)

    assert read_run(tmp_path, "{experiment}/runs/{run}", path) == [
        {
            "experiment": "exp",
            "id": "brave-fox",
            "folder": "exp/runs/brave-fox",
            "created": "2026-10-17T00:00:00Z",
            "ended": "2026-10-17T00:01:00Z",
            "exit_code": 0,
            "error": None,
            "stdout": "exp/runs/brave-fox/stdout.log",
            "stderr": "exp/runs/brave-fox/stderr.log",
            "params": '{"model": "opus", "effort": "low"}',
            "run": json.dumps(run),
        }
    ]


def test_leaves_missing_fields_empty(tmp_path: Path) -> None:
    path = write_run(tmp_path / "data" / "exp" / "r1", {})

    [row] = read_run(tmp_path, "data/{experiment}/{run}", path)

    assert (
        row["experiment"],
        row["id"],
        row["ended"],
        row["params"],
        row["run"],
    ) == ("exp", "r1", None, "{}", "{}")


def test_skips_a_run_json_outside_the_template(tmp_path: Path) -> None:
    path = write_run(tmp_path / "exp" / "runs" / "a" / "b", {})

    assert read_run(tmp_path, "{experiment}/runs/{run}", path) == []
