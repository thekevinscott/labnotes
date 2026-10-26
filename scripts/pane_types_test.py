import json
import stat
from pathlib import Path

import pytest

from pane_types import lay_types, stub_home


def fake_claude(tmp_path: Path, body: str) -> str:
    claude = tmp_path / "claude"
    claude.write_text(f"#!/bin/sh\n{body}\n")
    claude.chmod(claude.stat().st_mode | stat.S_IEXEC)
    return str(claude)


def test_stub_home_trusts_the_mod(tmp_path: Path) -> None:
    stub_home(tmp_path / "home", tmp_path / "mod")
    state = json.loads((tmp_path / "home" / ".claude.json").read_text())
    assert state["hasCompletedOnboarding"]
    assert state["projects"][str(tmp_path / "mod")]["hasTrustDialogAccepted"]


def test_stops_claude_once_the_types_are_laid(tmp_path: Path) -> None:
    mod = tmp_path / "mod"
    mod.mkdir()
    claude = fake_claude(
        tmp_path,
        "test -t 0 || exit 3\nmkdir -p .claude-plugin/types\n"
        "echo {} > .claude-plugin/types/tsconfig.json\necho {} > tsconfig.json\n"
        "sleep 30",
    )
    lay_types(mod, claude, timeout=10)
    assert (mod / ".claude-plugin" / "types" / "tsconfig.json").exists()


def test_fails_when_claude_exits_first(tmp_path: Path) -> None:
    mod = tmp_path / "mod"
    mod.mkdir()
    with pytest.raises(SystemExit, match="exited 3"):
        lay_types(mod, fake_claude(tmp_path, "exit 3"), timeout=10)


def test_fails_when_no_types_appear(tmp_path: Path) -> None:
    mod = tmp_path / "mod"
    mod.mkdir()
    with pytest.raises(SystemExit, match="no types"):
        lay_types(mod, fake_claude(tmp_path, "sleep 30"), timeout=1)
