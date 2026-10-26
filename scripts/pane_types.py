#!/usr/bin/env python3
"""Lay the pane mod's generated types so `tsc -p skills/labnotes` can run.

Claude Code writes `.claude-plugin/types/` and `tsconfig.json` beside a mod
only when an interactive session loads it; no command does it. So this starts
`claude --plugin-dir <mod>` in a pseudo-terminal, with a stub home that needs
no account, and stops it once the types are there.
"""

import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "skills" / "labnotes"


def stub_home(home: Path, project: Path) -> None:
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"apiKeyHelper": "echo sk-ant-types-dummy"})
    )
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "projects": {str(project): {"hasTrustDialogAccepted": True}},
            }
        )
    )


def lay_types(mod: Path, claude: str = "claude", timeout: float = 60) -> None:
    done = mod / ".claude-plugin" / "types" / "tsconfig.json"
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        stub_home(home, mod)
        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
        }
        for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            env.pop(key, None)
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [claude, "--plugin-dir", str(mod)],
            cwd=mod,
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
        os.close(slave)
        deadline = time.monotonic() + timeout
        try:
            while not (done.exists() and (mod / "tsconfig.json").exists()):
                if process.poll() is not None:
                    raise SystemExit(
                        f"claude exited {process.returncode} before laying types"
                    )
                if time.monotonic() > deadline:
                    raise SystemExit(f"no types under {done.parent} after {timeout}s")
                # Drain the terminal so claude never blocks on a full buffer.
                if select.select([master], [], [], 0.2)[0]:
                    try:
                        os.read(master, 65536)
                    except OSError:
                        pass
        finally:
            process.kill()
            process.wait()
            os.close(master)


if __name__ == "__main__":
    lay_types(Path(sys.argv[1]) if len(sys.argv) > 1 else MOD)
