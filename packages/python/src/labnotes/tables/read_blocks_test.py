from pathlib import Path

from labnotes.tables.read_blocks import read_blocks


def write_log(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_reads_a_block_log_row_with_its_size(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/runs/g1/brave-fox/log.jsonl", "{}\n")

    assert read_blocks(tmp_path, "{experiment}/runs/{run}", path) == [
        {"experiment": "exp", "run": "g1/brave-fox", "size": 3}
    ]


def test_skips_a_path_outside_the_runs_template(tmp_path: Path) -> None:
    path = write_log(tmp_path / "exp/files/log.jsonl", "{}\n")

    assert read_blocks(tmp_path, "data/{experiment}/{run}", path) == []


def test_names_the_one_experiment_when_the_template_has_none(tmp_path: Path) -> None:
    path = write_log(tmp_path / "runs/brave-fox/log.jsonl", "{}\n")

    assert read_blocks(tmp_path, "runs/{run}", path, experiment="study") == [
        {"experiment": "study", "run": "brave-fox", "size": 3}
    ]
