from pathlib import Path

from labnotes.latest_log import latest_log


def test_falls_back_to_the_single_log(tmp_path: Path) -> None:
    assert latest_log(tmp_path, "stdout") == tmp_path / "stdout.log"


def test_follows_the_newest_invocation_log(tmp_path: Path) -> None:
    for name in (
        "stdout.log",
        "stdout-20261102-090000-000000.txt",
        "stdout-20261102-100000-000000.txt",
        "stderr-20261102-110000-000000.txt",
    ):
        (tmp_path / name).write_text("")

    assert latest_log(tmp_path, "stdout") == (
        tmp_path / "stdout-20261102-100000-000000.txt"
    )
