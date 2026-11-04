"""Report a non-blocking perf failure in the job summary and PR discussion."""

import json
import os
import subprocess
from pathlib import Path


def report(outcome: str, environment: dict[str, str]) -> None:
    if outcome == "success":
        return

    repository = environment["GITHUB_REPOSITORY"]
    run_url = (
        f"{environment['GITHUB_SERVER_URL']}/{repository}/actions/runs/"
        f"{environment['GITHUB_RUN_ID']}"
    )
    message = f"Perf suite failed. See [workflow run]({run_url}) for the test output."
    with Path(environment["GITHUB_STEP_SUMMARY"]).open("a") as summary:
        summary.write(f"## Perf suite\n\n{message}\n")

    event = json.loads(Path(environment["GITHUB_EVENT_PATH"]).read_text())
    if "pull_request" not in event:
        return
    number = event["pull_request"]["number"]
    result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repository}/issues/{number}/comments",
            "-f",
            f"body={message}",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print(f"Could not post perf comment: {result.stderr.strip()}")


if __name__ == "__main__":
    report(os.environ["PERF_OUTCOME"], dict(os.environ))
