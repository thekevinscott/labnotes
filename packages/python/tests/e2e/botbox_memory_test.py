import json
import os
import subprocess
from pathlib import Path


def test_installed_labnotes_counts_container_memory_from_botbox_labels(
    botbox_memory_project: Path, botbox_caller_labels: str, uvx: dict[str, str]
) -> None:
    root = botbox_memory_project
    result = subprocess.run(
        [
            "uvx",
            "labnotes",
            "-c",
            str(root / ".labnotes.toml"),
            "experiments",
            "exp",
            "run",
        ],
        env={**os.environ, **uvx, "BOTBOX_LABELS": botbox_caller_labels},
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert "1 passed, 0 failed." in result.stdout
    [record] = root.glob("exp/runs/*/run.json")
    folder = record.parent
    assert json.loads(record.read_text())["exit_code"] == 0
    assert (folder / "stdout.log").read_text().strip() == "200000000"
    for hook in ("setup", "teardown"):
        assert (root / f"{hook}-labels.txt").read_text() == botbox_caller_labels
    samples = [
        json.loads(line) for line in (folder / "memory.jsonl").read_text().splitlines()
    ]
    assert max(sample["rss"] for sample in samples) > 200_000_000
    assert (folder / "botbox-labels.txt").read_text() == (
        f"{botbox_caller_labels}\nlabnotes.run={folder.resolve()}"
    )
