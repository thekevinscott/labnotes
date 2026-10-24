from pathlib import Path

from labnotes.tables.read_memory import read_memory


def write_samples(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


FIRST = '{"time": 10.5, "rss": 100, "processes": 1}\n'
SECOND = '{"time": 15.5, "rss": 300, "processes": 2}\n'


def test_reads_one_row_per_sample(tmp_path: Path) -> None:
    path = write_samples(
        tmp_path / "exp/runs/g1/brave-fox/memory.jsonl", FIRST + SECOND
    )

    assert read_memory(tmp_path, "{experiment}/runs/{run}", path) == [
        {
            "experiment": "exp",
            "run": "g1/brave-fox",
            "line": 0,
            "time": 10.5,
            "rss": 100,
            "processes": 1,
        },
        {
            "experiment": "exp",
            "run": "g1/brave-fox",
            "line": 1,
            "time": 15.5,
            "rss": 300,
            "processes": 2,
        },
    ]


def test_skips_a_last_line_cut_off_mid_write(tmp_path: Path) -> None:
    path = write_samples(
        tmp_path / "exp/runs/r1/memory.jsonl", FIRST + '{"time": 15.5, "rss": 3'
    )

    assert [
        row["line"] for row in read_memory(tmp_path, "{experiment}/runs/{run}", path)
    ] == [0]


def test_skips_lines_that_are_not_samples(tmp_path: Path) -> None:
    path = write_samples(tmp_path / "exp/runs/r1/memory.jsonl", "\n5\n[]\n" + SECOND)

    rows = read_memory(tmp_path, "{experiment}/runs/{run}", path)

    assert [(row["line"], row["rss"]) for row in rows] == [(3, 300)]


def test_leaves_a_missing_field_empty(tmp_path: Path) -> None:
    path = write_samples(tmp_path / "exp/runs/r1/memory.jsonl", '{"rss": 7}\n')

    [row] = read_memory(tmp_path, "{experiment}/runs/{run}", path)

    assert (row["time"], row["rss"], row["processes"]) == (None, 7, None)


def test_skips_a_path_outside_the_runs_template(tmp_path: Path) -> None:
    path = write_samples(tmp_path / "exp/files/memory.jsonl", FIRST)

    assert read_memory(tmp_path, "data/{experiment}/{run}", path) == []


def test_names_the_one_experiment_when_the_template_has_none(tmp_path: Path) -> None:
    path = write_samples(tmp_path / "runs/brave-fox/memory.jsonl", FIRST)

    [row] = read_memory(tmp_path, "runs/{run}", path, experiment="study")

    assert (row["experiment"], row["run"]) == ("study", "brave-fox")
