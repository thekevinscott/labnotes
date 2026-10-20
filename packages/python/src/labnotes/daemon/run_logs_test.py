from pathlib import Path

from labnotes.daemon.run_logs import RunLogs


def output(run: str, stream: str, line: str) -> dict[str, object]:
    return {
        "event": "output",
        "experiment": "exp",
        "run": run,
        "stream": stream,
        "line": line,
    }


def test_reports_the_last_complete_line_of_each_log(tmp_path: Path) -> None:
    logs = RunLogs()
    logs.add("exp", "r1", tmp_path)
    (tmp_path / "stdout.log").write_bytes(b"one\ntwo\nthr")
    (tmp_path / "stderr.log").write_bytes(b"oops\n")

    assert logs.latest() == [
        output("r1", "stdout", "two"),
        output("r1", "stderr", "oops"),
    ]


def test_reports_only_lines_written_since_the_last_read(tmp_path: Path) -> None:
    logs = RunLogs()
    logs.add("exp", "r1", tmp_path)
    log = tmp_path / "stdout.log"
    log.write_bytes(b"one\nth")
    logs.latest()

    assert logs.latest() == []
    with log.open("ab") as more:
        more.write(b"ree\n")
    assert logs.latest() == [output("r1", "stdout", "three")]
    assert logs.latest() == []


def test_skips_blank_lines_and_keeps_the_end_of_a_progress_bar(
    tmp_path: Path,
) -> None:
    logs = RunLogs()
    logs.add("exp", "r1", tmp_path)
    (tmp_path / "stdout.log").write_bytes(b"10%\r50%\r 90% \n\n  \n")

    assert logs.latest() == [output("r1", "stdout", "90%")]


def test_ignores_logs_not_written_yet(tmp_path: Path) -> None:
    logs = RunLogs()
    logs.add("exp", "r1", tmp_path)

    assert logs.latest() == []


def test_stops_reading_a_dropped_run(tmp_path: Path) -> None:
    logs = RunLogs()
    logs.add("exp", "r1", tmp_path)
    logs.drop("exp", "r1")
    logs.drop("exp", "r2")
    (tmp_path / "stdout.log").write_bytes(b"one\n")

    assert logs.latest() == []


def test_replaces_undecodable_bytes(tmp_path: Path) -> None:
    logs = RunLogs()
    logs.add("exp", "r1", tmp_path)
    (tmp_path / "stdout.log").write_bytes(b"caf\xff\n")

    assert logs.latest() == [output("r1", "stdout", "caf�")]
