import asyncio
import json
from pathlib import Path
from typing import Any
from unittest import mock

from labnotes.daemon.reads import Reads
from labnotes.models import LabnotesConfig
from labnotes.tables.open_experiment_tables import open_experiment_tables


def request(**params: str) -> mock.Mock:
    return mock.Mock(headers={}, path_params=params)


def parse(frames: list[str]) -> list[tuple[str, str, Any]]:
    parsed = []
    for frame in frames:
        fields = dict(line.split(": ", 1) for line in frame.splitlines() if line)
        parsed.append((fields["event"], fields["id"], json.loads(fields["data"])))
    return parsed


def test_runs_and_files_answer_from_real_tables(tmp_path: Path) -> None:
    folder = tmp_path / "exp/runs/20261114-000001-quiet-pond"
    folder.mkdir(parents=True)
    (tmp_path / "exp/experiment.toml").write_text('command = "true"\n')
    runs = {
        "20261114-000001-quiet-pond": {"created": "t1", "exit_code": 0},
        "b": {"created": "t2"},
        "c": {"created": "t3", "exit_code": 0, "ended_by": "stop"},
        "d": {"created": "t4", "exit_code": 2},
        "e": {"created": "t5", "error": "boom"},
    }
    for run, record in runs.items():
        (tmp_path / "exp/runs" / run).mkdir(parents=True, exist_ok=True)
        (tmp_path / "exp/runs" / run / "run.json").write_text(json.dumps(record))
    (folder / "out.log").write_text("12345")
    (folder / "memory.jsonl").write_text(
        '{"time": 1, "rss": 10, "processes": 1}\n{"time": 2, "rss": 20, "processes": 1}\n'
    )
    config = LabnotesConfig(
        path=tmp_path / ".labnotes.toml",
        root=tmp_path,
        experiments="{experiment}",
        files="{experiment}/files/",
        runs="{experiment}/runs/{run}",
    )

    async def first(response: Any) -> tuple[str, str, Any]:
        async for frame in response.body_iterator:
            return parse([str(frame)])[0]
        raise AssertionError("no event")

    async def check() -> None:
        reads = Reads(tmp_path, open_experiment_tables(config, "exp"))
        _, _, listed = await first(await reads.runs(request()))
        sizes = {
            run: sum(f.stat().st_size for f in (tmp_path / "exp/runs" / run).iterdir())
            for run in runs
        }
        assert listed == [
            {
                "id": "20261114-000001-quiet-pond",
                "name": "quiet-pond",
                "started": "t1",
                "status": "succeeded",
                "memory": 20,
                "size": sizes["20261114-000001-quiet-pond"],
            },
            {"id": "b", "name": "b", "started": "t2", "status": "running"}
            | {"memory": None, "size": sizes["b"]},
            {"id": "c", "name": "c", "started": "t3", "status": "stop"}
            | {"memory": None, "size": sizes["c"]},
            {"id": "d", "name": "d", "started": "t4", "status": "failed"}
            | {"memory": None, "size": sizes["d"]},
            {"id": "e", "name": "e", "started": "t5", "status": "failed"}
            | {"memory": None, "size": sizes["e"]},
        ]
        _, _, files = await first(
            await reads.run_path(request(path="20261114-000001-quiet-pond/files"))
        )
        assert [(file["name"], file["size"]) for file in files] == [
            ("memory.jsonl", (folder / "memory.jsonl").stat().st_size),
            ("out.log", 5),
            ("run.json", (folder / "run.json").stat().st_size),
        ]

    asyncio.run(check())
