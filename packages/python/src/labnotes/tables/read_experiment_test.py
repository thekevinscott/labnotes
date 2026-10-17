from pathlib import Path

from labnotes.tables.read_experiment import read_experiment


def write_config(path: Path, text: str) -> str:
    path.mkdir(parents=True)
    (path / "experiment.toml").write_text(text, encoding="utf-8")
    return str(path / "experiment.toml")


def test_reads_the_experiment_config(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "exp", 'command = "run"\nrepeats = 2\n[params]\nm = ["a"]\n'
    )

    assert read_experiment(tmp_path, "{experiment}", path) == [
        {
            "experiment": "exp",
            "config": '{"command": "run", "repeats": 2, "params": {"m": ["a"]}}',
        }
    ]


def test_skips_a_config_outside_the_template(tmp_path: Path) -> None:
    path = write_config(tmp_path / "other" / "exp", "")

    assert read_experiment(tmp_path, "notes/{experiment}", path) == []
