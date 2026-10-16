import asyncio
import json
from pathlib import Path

from labnotes.open_experiments import open_experiments


async def query_all(
    folder: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    db = open_experiments(folder)
    await db.ready()
    experiments = await db.query("SELECT * FROM experiments")
    notes = await db.query("SELECT experiment, name FROM notes")
    return experiments, notes


def test_indexes_designs_and_notes_per_experiment(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "design.yaml").write_text("study: s1\n", encoding="utf-8")
    (tmp_path / "a" / "PLAN.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "loose.md").write_text("not an experiment\n", encoding="utf-8")

    experiments, notes = asyncio.run(query_all(tmp_path))

    assert [(e["name"], e["study"]) for e in experiments] == [("a", "s1")]
    assert json.loads(str(experiments[0]["design"])) == {"study": "s1"}
    assert notes == [{"experiment": "a", "name": "PLAN.md"}]
