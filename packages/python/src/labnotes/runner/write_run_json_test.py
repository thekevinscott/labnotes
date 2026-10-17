import json
from pathlib import Path

from labnotes.runner.write_run_json import write_run_json


def test_writes_run_json(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{}", encoding="utf-8")

    write_run_json(tmp_path, {"params": {"m": "a"}, "ended": None})

    assert json.loads((tmp_path / "run.json").read_text(encoding="utf-8")) == {
        "params": {"m": "a"},
        "ended": None,
    }
    assert [p.name for p in tmp_path.iterdir()] == ["run.json"]
