import asyncio
from pathlib import Path

from labnotes.list_experiments import list_experiments

CONFIG = """
[[table]]
name = "runs"
glob = "runs/*.json"
on-file = "cat"
ddl = "CREATE TABLE runs (study TEXT)"
"""


def test_counts_runs_per_experiment_by_study(tmp_path: Path) -> None:
    experiments = tmp_path / "experiments"
    for name, study in [("a", "s1"), ("b", "s2")]:
        (experiments / name).mkdir(parents=True)
        (experiments / name / "design.yaml").write_text(
            f"study: {study}\n", encoding="utf-8"
        )
    data = tmp_path / "data"
    (data / "runs").mkdir(parents=True)
    (data / ".dirsql.toml").write_text(CONFIG, encoding="utf-8")
    for i in range(3):
        (data / "runs" / f"{i}.json").write_text('{"study": "s1"}\n', encoding="utf-8")

    assert asyncio.run(list_experiments(experiments, data)) == [
        {"name": "a", "study": "s1", "runs": 3},
        {"name": "b", "study": "s2", "runs": 0},
    ]
