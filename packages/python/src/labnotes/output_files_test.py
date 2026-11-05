import json
from pathlib import Path

import pytest

from labnotes.output_files import output_files


def write_run(folder: Path, run: object) -> None:
    (folder / "run.json").write_text(json.dumps(run), encoding="utf-8")


def test_names_a_runs_index_and_its_logs(tmp_path: Path) -> None:
    write_run(tmp_path, {"output": "output.jsonl"})

    assert output_files(tmp_path) == {
        "output": tmp_path / "output.jsonl",
        "stdout": tmp_path / "stdout.log",
        "stderr": tmp_path / "stderr.log",
    }


def test_names_the_latest_invocations_index_and_logs(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        {
            "output": "output-2.jsonl",
            "invocations": [
                {"stdout": "stdout-1.txt", "stderr": "stderr-1.txt"},
                {
                    "stdout": "stdout-2.txt",
                    "stderr": "stderr-2.txt",
                    "output": "output-2.jsonl",
                },
            ],
        },
    )

    assert output_files(tmp_path) == {
        "output": tmp_path / "output-2.jsonl",
        "stdout": tmp_path / "stdout-2.txt",
        "stderr": tmp_path / "stderr-2.txt",
    }


@pytest.mark.parametrize(
    "run",
    [
        {},
        {"output": None},
        {"output": "output.jsonl", "invocations": [{"stdout": "stdout-1.txt"}]},
        ["output.jsonl"],
    ],
)
def test_names_nothing_for_a_run_without_an_index(tmp_path: Path, run: object) -> None:
    write_run(tmp_path, run)

    assert output_files(tmp_path) is None


def test_names_nothing_without_a_run_record(tmp_path: Path) -> None:
    assert output_files(tmp_path) is None


def test_names_nothing_for_a_damaged_run_record(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_bytes(b'{"output": "\xff')

    assert output_files(tmp_path) is None


def test_reads_the_run_record_as_utf8(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_bytes('{"output": "é.jsonl"}'.encode())

    files = output_files(tmp_path)

    assert files is not None
    assert files["output"] == tmp_path / "é.jsonl"
