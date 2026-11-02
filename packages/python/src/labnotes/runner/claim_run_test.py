import fcntl
import os
from pathlib import Path

from labnotes.runner.claim_run import LOCK_FILE, claim_run


def test_names_the_lock_file() -> None:
    assert LOCK_FILE == "run.lock"


def test_creates_and_holds_the_lock_file(tmp_path: Path) -> None:
    lock = claim_run(tmp_path)

    assert lock is not None
    assert (tmp_path / "run.lock").exists()
    assert claim_run(tmp_path) is None
    os.close(lock)


def test_claims_a_lock_file_nobody_holds(tmp_path: Path) -> None:
    (tmp_path / "run.lock").write_text("left behind")

    lock = claim_run(tmp_path)

    assert lock is not None
    assert (tmp_path / "run.lock").read_text() == "left behind"
    os.close(lock)


def test_gives_way_to_another_holder(tmp_path: Path) -> None:
    with (tmp_path / "run.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)

        assert claim_run(tmp_path) is None

    lock = claim_run(tmp_path)
    assert lock is not None
    os.close(lock)
