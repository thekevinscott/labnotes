import json
from pathlib import Path

from labnotes.invocation_logs import invocation_logs


def write_run(folder: Path, run: object) -> None:
    (folder / "run.json").write_text(json.dumps(run))


def test_a_run_without_invocations_has_one_unlabeled_log(tmp_path: Path) -> None:
    assert invocation_logs(tmp_path, "stdout") == [(None, tmp_path / "stdout.log")]


def test_lists_every_invocation_in_order_with_a_label(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        {
            "invocations": [
                {"started": "2026-11-02T09:00:00Z", "stdout": "a.txt", "stderr": "b"},
                {"started": "2026-11-02T10:00:00Z", "stdout": "c.txt", "stderr": "d"},
            ]
        },
    )

    assert invocation_logs(tmp_path, "stdout") == [
        ("invocation 1 · 2026-11-02T09:00:00Z", tmp_path / "a.txt"),
        ("invocation 2 · 2026-11-02T10:00:00Z", tmp_path / "c.txt"),
    ]
    assert invocation_logs(tmp_path, "stderr")[1] == (
        "invocation 2 · 2026-11-02T10:00:00Z",
        tmp_path / "d",
    )


def test_labels_an_invocation_without_a_start_by_number(tmp_path: Path) -> None:
    write_run(tmp_path, {"invocations": [{"started": None, "stdout": "a.txt"}]})

    assert invocation_logs(tmp_path, "stdout") == [("invocation 1", tmp_path / "a.txt")]


def test_skips_an_invocation_without_a_log_but_keeps_numbering(tmp_path: Path) -> None:
    write_run(tmp_path, {"invocations": ["odd", {"stderr": "x"}, {"stdout": "c.txt"}]})

    assert invocation_logs(tmp_path, "stdout") == [("invocation 3", tmp_path / "c.txt")]


def test_keeps_a_recorded_name_inside_the_folder(tmp_path: Path) -> None:
    write_run(tmp_path, {"invocations": [{"stdout": "../../etc/passwd"}]})

    assert invocation_logs(tmp_path, "stdout") == [
        ("invocation 1", tmp_path / "passwd")
    ]


def test_falls_back_when_run_json_is_unreadable_or_odd(tmp_path: Path) -> None:
    fallback = [(None, tmp_path / "stdout.log")]
    (tmp_path / "run.json").write_text("{not json")
    assert invocation_logs(tmp_path, "stdout") == fallback

    runs: list[object] = [
        [],
        {},
        {"invocations": "x"},
        {"invocations": []},
        {"invocations": [{"stderr": "x.txt"}]},
    ]
    for run in runs:
        write_run(tmp_path, run)
        assert invocation_logs(tmp_path, "stdout") == fallback
