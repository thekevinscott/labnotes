import json
from pathlib import Path

from curtaincall import expect

from conftest import Tui


def test_installed_labnotes_counts_container_memory_from_botbox_labels(
    botbox_memory_project: Path, botbox_caller_labels: str, tui: Tui
) -> None:
    root = botbox_memory_project
    term = tui(
        root, "experiments", "exp", "run", env={"BOTBOX_LABELS": botbox_caller_labels}
    )
    expect(term.get_by_text("1 passed, 0 failed.")).to_be_visible(timeout=120)
    term.write("[")
    expect(term.get_by_text("200000000")).to_be_visible()
    tui.quit(term)

    [record] = root.glob("exp/runs/*/run.json")
    folder = record.parent
    for hook in ("setup", "teardown"):
        assert (root / f"{hook}-labels.txt").read_text() == botbox_caller_labels
    samples = [
        json.loads(line) for line in (folder / "memory.jsonl").read_text().splitlines()
    ]
    assert max(sample["rss"] for sample in samples) > 200_000_000
    assert (folder / "botbox-labels.txt").read_text() == (
        f"{botbox_caller_labels}\nlabnotes.run={folder.resolve()}"
    )
