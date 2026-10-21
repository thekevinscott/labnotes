from pathlib import Path

from labnotes.tables.read_experiment import read_experiment


def write_config(path: Path, text: str) -> str:
    path.mkdir(parents=True)
    (path / "experiment.toml").write_text(text, encoding="utf-8")
    return str(path / "experiment.toml")


def test_reads_the_experiment_config(tmp_path: Path) -> None:
    source = 'command = "run"\nrepeats = 2\n[params]\nm = ["a"]\n'
    path = write_config(tmp_path / "exp", source)

    assert read_experiment(tmp_path, "{experiment}", path) == [
        {
            "experiment": "exp",
            "config": '{"command": "run", "repeats": 2, "params": {"m": ["a"]}}',
            "source": source,
        }
    ]


def test_skips_a_config_outside_the_template(tmp_path: Path) -> None:
    path = write_config(tmp_path / "other" / "exp", "")

    assert read_experiment(tmp_path, "notes/{experiment}", path) == []


def test_names_the_root_config_after_the_one_experiment(tmp_path: Path) -> None:
    path = tmp_path / "experiment.toml"
    path.write_text('name = "Study"\n', encoding="utf-8")

    [row] = read_experiment(tmp_path, "", str(path), experiment="study")

    assert row["experiment"] == "study"


def test_layers_the_config_over_the_defaults(tmp_path: Path) -> None:
    path = write_config(tmp_path / "exp", '[params]\nm = ["b"]\n')

    [row] = read_experiment(
        tmp_path,
        "{experiment}",
        path,
        defaults={"command": "go", "params": {"m": ["a"], "n": [1]}},
    )

    assert row["config"] == ('{"command": "go", "params": {"m": ["b"], "n": [1]}}')
