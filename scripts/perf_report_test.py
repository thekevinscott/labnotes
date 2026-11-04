import json
from pathlib import Path
from unittest import mock

from perf_report import report


def environment(tmp_path: Path, event: dict[str, object]) -> dict[str, str]:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    return {
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "123",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "GITHUB_EVENT_PATH": str(event_path),
        "GH_TOKEN": "token",
    }


def test_success_neither_reports_nor_comments(tmp_path: Path) -> None:
    env = environment(tmp_path, {"pull_request": {"number": 4}})
    with mock.patch("perf_report.subprocess.run") as run:
        report("success", env)
    assert not Path(env["GITHUB_STEP_SUMMARY"]).exists()
    run.assert_not_called()


def test_failure_writes_summary_and_comments_on_pr(tmp_path: Path) -> None:
    env = environment(tmp_path, {"pull_request": {"number": 4}})
    with mock.patch("perf_report.subprocess.run") as run:
        report("failure", env)
    message = Path(env["GITHUB_STEP_SUMMARY"]).read_text()
    assert "Perf suite failed" in message
    assert "https://github.com/owner/repo/actions/runs/123" in message
    assert run.call_args.args[0][:5] == [
        "gh",
        "api",
        "-X",
        "POST",
        "repos/owner/repo/issues/4/comments",
    ]
    assert "body=Perf suite failed" in run.call_args.args[0][6]


def test_push_failure_writes_summary_without_comment(tmp_path: Path) -> None:
    env = environment(tmp_path, {"ref": "refs/heads/main"})
    with mock.patch("perf_report.subprocess.run") as run:
        report("failure", env)
    assert "Perf suite failed" in Path(env["GITHUB_STEP_SUMMARY"]).read_text()
    run.assert_not_called()
