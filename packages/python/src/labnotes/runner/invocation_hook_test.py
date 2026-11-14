import json
import asyncio
from pathlib import Path

import pytest

from labnotes.runner.invocation_hook import invocation_hook


def test_runs_the_command_from_the_root(tmp_path: Path) -> None:
    asyncio.run(
        invocation_hook(tmp_path, "setup", "touch made", None, tmp_path / "logs")
    )

    assert (tmp_path / "made").exists()


def test_passes_the_invocations_environment(tmp_path: Path) -> None:
    asyncio.run(
        invocation_hook(
            tmp_path,
            "setup",
            'printf %s "$VALUE" > made',
            {"VALUE": "from-cli"},
            tmp_path / "logs",
        )
    )

    assert (tmp_path / "made").read_text() == "from-cli"


def test_fails_with_the_exit_code_and_stderr(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        asyncio.run(
            invocation_hook(
                tmp_path, "setup", "echo broke >&2; exit 3", None, tmp_path / "logs"
            )
        )

    assert str(error.value) == "setup command echo broke >&2; exit 3 exited 3: broke"


def test_fails_without_detail_when_stderr_is_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        asyncio.run(
            invocation_hook(tmp_path, "teardown", "exit 1", None, tmp_path / "logs")
        )

    assert str(error.value) == "teardown command exit 1 exited 1"


def test_fails_when_a_signal_ends_the_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        asyncio.run(
            invocation_hook(tmp_path, "setup", "kill -9 $$", None, tmp_path / "logs")
        )

    assert str(error.value) == "setup command kill -9 $$ exited -9"


def test_writes_stdout_and_stderr_to_the_folder(tmp_path: Path) -> None:
    folder = tmp_path / "logs" / "setup"

    asyncio.run(
        invocation_hook(tmp_path, "setup", "echo out; echo err >&2", None, folder)
    )

    assert (folder / "stdout.log").read_text() == "out\n"
    assert (folder / "stderr.log").read_text() == "err\n"


def test_records_the_hooks_metadata(tmp_path: Path) -> None:
    folder = tmp_path / "logs"

    with pytest.raises(ValueError):
        asyncio.run(invocation_hook(tmp_path, "setup", "exit 2", None, folder, ["r1"]))

    metadata = json.loads((folder / "metadata.json").read_text())
    assert metadata["hook"] == "setup"
    assert metadata["command"] == "exit 2"
    assert metadata["runs"] == ["r1"]
    assert metadata["exit_code"] == 2
    assert metadata["error"] == "setup command exit 2 exited 2"
    assert metadata["started"] <= metadata["ended"]


def test_reuses_an_existing_log_folder(tmp_path: Path) -> None:
    folder = tmp_path / "logs"
    folder.mkdir()

    asyncio.run(invocation_hook(tmp_path, "setup", "true", None, folder))

    assert (folder / "metadata.json").exists()


def test_writes_metadata_as_indented_json_before_and_after(tmp_path: Path) -> None:
    folder = tmp_path / "logs"

    asyncio.run(
        invocation_hook(
            tmp_path, "setup", "cp logs/metadata.json during.json", None, folder
        )
    )

    for written in (tmp_path / "during.json", folder / "metadata.json"):
        text = written.read_text()
        assert text == json.dumps(json.loads(text), indent=2) + "\n"


def test_hands_over_the_process_while_it_runs(tmp_path: Path) -> None:
    seen: list[int | None] = []

    def started(process: asyncio.subprocess.Process) -> None:
        seen.append(process.returncode)

    asyncio.run(
        invocation_hook(
            tmp_path, "setup", "true", None, tmp_path / "logs", started=started
        )
    )

    assert seen == [None]
