from unittest import mock
from pathlib import Path

from labnotes.runner.write_run_json import write_run_json


def test_writes_run_json(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{}", encoding="utf-8")

    write_run_json(tmp_path, {"params": {"m": "a"}, "ended": None})

    assert (tmp_path / "run.json").read_text(encoding="utf-8") == (
        '{\n  "params": {\n    "m": "a"\n  },\n  "ended": null\n}\n'
    )
    assert [p.name for p in tmp_path.iterdir()] == ["run.json"]


def test_tmp_name_includes_the_pid_and_is_gone_after(tmp_path: Path) -> None:
    with (
        mock.patch("labnotes.runner.write_run_json.os.getpid", return_value=4242),
        mock.patch.object(
            Path, "replace", autospec=True, side_effect=Path.replace
        ) as replace,
    ):
        write_run_json(tmp_path, {})

    assert replace.call_args.args[0].name == "run.json.4242.tmp"
    assert [p.name for p in tmp_path.iterdir()] == ["run.json"]
