from pathlib import Path

from labnotes.tables.read_log import read_log


def write_log(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_reads_a_log_row_with_its_size(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/runs/brave-fox/stderr.log", "boom\n")

    assert read_log(tmp_path, "{experiment}/runs/{run}", path) == [
        {"experiment": "exp", "run": "brave-fox", "stream": "stderr", "size": 5}
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
        {"experiment": "study", "run": "brave-fox", "stream": "stdout", "size": 3}
    ]
