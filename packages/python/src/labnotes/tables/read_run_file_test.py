import os
from pathlib import Path

from labnotes.tables.read_run_file import read_run_file


def write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(0, 1_000_000_007))
    return str(path)


def test_reads_any_file_in_a_run_folder(tmp_path: Path) -> None:
    path = write(tmp_path / "exp/runs/brave-fox/out/result.json", "{}")

    assert read_run_file(tmp_path, "{experiment}/runs/{run}", path) == [
        {
            "experiment": "exp",
            "path": "exp/runs/brave-fox/out/result.json",
            "size": 2,
            "mtime_ns": 1_000_000_007,
        }
    ]


def test_skips_a_path_outside_the_runs_template(tmp_path: Path) -> None:
    path = write(tmp_path / "exp/files/notes.md", "x")

    assert read_run_file(tmp_path, "{experiment}/runs/{run}", path) == []


def test_names_the_one_experiment_when_the_template_has_none(tmp_path: Path) -> None:
    path = write(tmp_path / "runs/brave-fox/stdout.log", "hi\n")

    [row] = read_run_file(tmp_path, "runs/{run}", path, experiment="study")

    assert (row["experiment"], row["path"]) == ("study", "runs/brave-fox/stdout.log")
