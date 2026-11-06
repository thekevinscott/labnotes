import json
from pathlib import Path

from labnotes.latest_log import latest_log


def write_run(folder: Path, run: object) -> None:
    (folder / "run.json").write_text(json.dumps(run))


def test_falls_back_to_the_single_log(tmp_path: Path) -> None:
    assert latest_log(tmp_path, "stdout") == tmp_path / "stdout.log"


def test_follows_the_last_invocation_in_run_json(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        {
            "invocations": [
                {"stdout": "stdout-1.txt", "stderr": "stderr-1.txt"},
                {"stdout": "stdout-2.txt", "stderr": "stderr-2.txt"},
            ]
        },
    )

    assert latest_log(tmp_path, "stdout") == tmp_path / "stdout-2.txt"
    assert latest_log(tmp_path, "stderr") == tmp_path / "stderr-2.txt"


def test_ignores_files_a_script_writes(tmp_path: Path) -> None:
    for name in ("stdout.log", "stdout-summary.txt", "stdout-best.txt"):
        (tmp_path / name).write_text("")

    assert latest_log(tmp_path, "stdout") == tmp_path / "stdout.log"


def test_ignores_files_beside_the_recorded_invocation(tmp_path: Path) -> None:
    write_run(
        tmp_path, {"invocations": [{"stdout": "stdout-20260101-000000-000000.txt"}]}
    )
    (tmp_path / "stdout-summary.txt").write_text("")

    assert latest_log(tmp_path, "stdout") == (
        tmp_path / "stdout-20260101-000000-000000.txt"
    )


def test_keeps_a_recorded_name_inside_the_folder(tmp_path: Path) -> None:
    write_run(tmp_path, {"invocations": [{"stdout": "../../etc/passwd"}]})

    assert latest_log(tmp_path, "stdout") == tmp_path / "passwd"


def test_falls_back_when_run_json_is_unreadable_or_odd(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{not json")
    assert latest_log(tmp_path, "stdout") == tmp_path / "stdout.log"

    runs: list[object] = [
        [],
        {},
        {"invocations": []},
        {"invocations": [{"stderr": "x.txt"}]},
    ]
    for run in runs:
        write_run(tmp_path, run)
        assert latest_log(tmp_path, "stdout") == tmp_path / "stdout.log"
