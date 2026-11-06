from pathlib import Path

from labnotes.tables.read_log import read_log


def write_log(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_reads_a_log_row_with_its_size(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/runs/brave-fox/stderr.log", "boom\n")

    assert read_log(tmp_path, "{experiment}/runs/{run}", path) == [
        {
            "experiment": "exp",
            "run": "brave-fox",
            "stream": "stderr",
            "file": "stderr.log",
            "size": 5,
        }
    ]


def test_reads_a_nested_run(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/runs/g1/quiet-river/stdout.log", "")

    [row] = read_log(tmp_path, "{experiment}/runs/{run}", path)

    assert (row["run"], row["stream"], row["size"]) == ("g1/quiet-river", "stdout", 0)


def test_skips_other_logs_a_script_writes(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/runs/r1/debug.log", "x")

    assert read_log(tmp_path, "{experiment}/runs/{run}", path) == []


def test_skips_a_path_outside_the_runs_template(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/files/stdout.log", "x")

    assert read_log(tmp_path, "data/{experiment}/{run}", path) == []


def test_names_the_one_experiment_when_the_template_has_none(tmp_path: Path) -> None:
    path = write_log(tmp_path / "runs/brave-fox/stdout.log", "hi\n")

    assert read_log(tmp_path, "runs/{run}", path, experiment="study") == [
        {
            "experiment": "study",
            "run": "brave-fox",
            "stream": "stdout",
            "file": "stdout.log",
            "size": 3,
        }
    ]


def test_reads_one_invocation_log_of_a_run_that_continues(tmp_path: Path) -> None:
    name = "stderr-20261102-150000-000001.txt"
    path = write_log(tmp_path / f"exp/runs/brave-fox/{name}", "boom\n")

    [row] = read_log(tmp_path, "{experiment}/runs/{run}", path)

    assert (row["run"], row["stream"], row["file"]) == ("brave-fox", "stderr", name)


def test_skips_text_files_that_are_not_invocation_logs(tmp_path: Path) -> None:
    for name in (
        "stdout.txt",
        "stdout-.txt",
        "notes-1.txt",
        "stdout-1.log",
        "stdout-summary.txt",
        "stdout-20261102-150000-00000.txt",
    ):
        path = write_log(tmp_path / f"exp/runs/r1/{name}", "x")

        assert read_log(tmp_path, "{experiment}/runs/{run}", path) == []
