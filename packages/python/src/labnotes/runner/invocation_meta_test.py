import asyncio
import shlex
import sys
from pathlib import Path

import pytest

from labnotes.runner.invocation_meta import invocation_meta


def python(code: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def meta(root: Path, command: str) -> dict[str, object]:
    return asyncio.run(invocation_meta(root, command))


def test_reads_one_json_object_from_stdout(tmp_path: Path) -> None:
    command = python('print(\'{"commit": "abc", "dirty": false}\')')

    assert meta(tmp_path, command) == {"commit": "abc", "dirty": False}


def test_runs_from_the_root(tmp_path: Path) -> None:
    command = python("import json, os; print(json.dumps({'cwd': os.getcwd()}))")

    assert meta(tmp_path, command) == {"cwd": str(tmp_path)}


def test_passes_the_invocations_environment(tmp_path: Path) -> None:
    command = python(
        "import json, os; print(json.dumps({'value': os.environ['VALUE']}))"
    )

    assert asyncio.run(invocation_meta(tmp_path, command, {"VALUE": "from-cli"})) == {
        "value": "from-cli"
    }


def test_fails_on_a_non_zero_exit_with_the_command_and_its_stderr(
    tmp_path: Path,
) -> None:
    command = python("import sys; sys.stderr.write('no repo\\n'); sys.exit(3)")

    with pytest.raises(ValueError) as error:
        meta(tmp_path, command)

    assert str(error.value) == f"meta command {command} exited 3: no repo"


def test_fails_on_output_that_is_not_json(tmp_path: Path) -> None:
    command = python("import sys; print('abc'); sys.stderr.write('warned')")

    with pytest.raises(ValueError) as error:
        meta(tmp_path, command)

    assert str(error.value) == (
        f"meta command {command} didn't print a JSON object: warned"
    )


@pytest.mark.parametrize("output", ["[1, 2]", '"abc"', "3", "null"])
def test_fails_on_json_that_is_not_an_object(tmp_path: Path, output: str) -> None:
    command = python(f"print({output!r})")

    with pytest.raises(ValueError) as error:
        meta(tmp_path, command)

    assert str(error.value) == f"meta command {command} didn't print a JSON object"


def test_fails_when_a_signal_ends_the_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as error:
        meta(tmp_path, "echo '{}'; kill -TERM $$")

    assert str(error.value) == "meta command echo '{}'; kill -TERM $$ exited -15"
