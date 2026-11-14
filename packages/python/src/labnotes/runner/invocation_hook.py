import asyncio
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    return datetime.now(UTC).isoformat()


async def invocation_hook(
    root: Path,
    hook: str,
    command: str,
    environment: dict[str, str] | None,
    folder: Path,
    runs: Sequence[str] = (),
    started: Callable[[asyncio.subprocess.Process], None] = lambda process: None,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, object] = {
        "hook": hook,
        "command": command,
        "runs": list(runs),
        "started": now(),
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    with (
        (folder / "stdout.log").open("wb") as stdout,
        (folder / "stderr.log").open("wb") as stderr,
    ):
        # Same as runs: keep the script's own exit code when stop signals it.
        process = await asyncio.create_subprocess_shell(
            f"trap : TERM; {command}",
            cwd=root,
            stdout=stdout,
            stderr=stderr,
            env=environment,
        )
        started(process)
        await process.wait()
    error = None
    if process.returncode != 0:
        message = f"{hook} command {command} exited {process.returncode}"
        detail = (folder / "stderr.log").read_text(errors="replace").strip()
        error = f"{message}: {detail}" if detail else message
    metadata |= {"ended": now(), "exit_code": process.returncode, "error": error}
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    if error is not None:
        raise ValueError(error)
