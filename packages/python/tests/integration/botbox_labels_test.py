import json
import os
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest
from conftest import write

from labnotes.cli import main

CAPTURE = """
import json
import os
import sys
from pathlib import Path

record = {key: os.environ.get(key) for key in ("BOTBOX_LABELS", "LABNOTES_RUN")}
Path(sys.argv[1] + ".json").write_text(json.dumps(record))
if sys.argv[1] == "meta":
    print("{}")
"""
LABELS = "team=research\nproject=study"


@pytest.fixture(params=["unset", "caller", "config"])
def labeled_project(
    tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[tuple[Path, str | None]]:
    inherited = {
        key: value for key, value in os.environ.items() if key != "BOTBOX_LABELS"
    }
    configured = ""
    if request.param == "caller":
        inherited["BOTBOX_LABELS"] = LABELS
    elif request.param == "config":
        configured = f"[env]\nBOTBOX_LABELS = {json.dumps(LABELS)}\n"
    write(tmp_path / ".labnotes.toml", '[experiments]\npath = "{experiment}"\n')
    write(tmp_path / "capture.py", CAPTURE)
    command = shlex.join([sys.executable, "capture.py"])
    write(
        tmp_path / "exp" / "experiment.toml",
        f'command = "{command} run"\n'
        f'meta = "{command} meta"\n'
        f'setup = "{command} setup"\n'
        f'teardown = "{command} teardown"\n' + configured,
    )
    with mock.patch.dict(os.environ, inherited, clear=True):
        with pytest.raises(SystemExit) as exit_info:
            main(["-c", str(tmp_path / ".labnotes.toml"), "experiments", "exp", "run"])
        assert exit_info.value.code == 0
        yield tmp_path, None if request.param == "unset" else LABELS


def test_run_receives_its_absolute_folder_label(
    labeled_project: tuple[Path, str | None],
) -> None:
    root, existing = labeled_project
    [run] = (root / "exp" / "runs").rglob("run.json")
    assert json.loads(run.read_text())["exit_code"] == 0
    record = json.loads((root / "run.json").read_text())
    folder = str(run.parent.resolve())
    label = f"labnotes.run={folder}"
    assert record == {
        "LABNOTES_RUN": folder,
        "BOTBOX_LABELS": f"{existing}\n{label}" if existing else label,
    }


def test_hooks_keep_existing_labels_without_a_run_label(
    labeled_project: tuple[Path, str | None],
) -> None:
    root, existing = labeled_project
    for hook in ("meta", "setup", "teardown"):
        assert json.loads((root / f"{hook}.json").read_text()) == {
            "LABNOTES_RUN": None,
            "BOTBOX_LABELS": existing,
        }
