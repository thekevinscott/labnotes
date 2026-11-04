"""Locate the private Unix socket and its on-disk discovery record."""

import hashlib
import os
import tempfile
from importlib.metadata import version
from pathlib import Path

from labnotes.models import LabnotesConfig
from labnotes.runner.run_state import journal_folder
from labnotes.runner.runs_parent import runs_parent


def daemon_key(config: LabnotesConfig, name: str) -> str:
    """Key an experiment by its resolved path and installed package version."""
    folder = config.root / config.experiments.replace("{experiment}", name)
    identity = f"{folder.resolve()}\0{version('labnotes')}"
    return hashlib.sha256(identity.encode()).hexdigest()[:16]


def runtime_folder() -> Path:
    """Keep socket names short even when the experiment path is deep."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    folder = (
        Path(runtime) / "labnotes"
        if runtime
        else Path(tempfile.gettempdir()) / f"labnotes-{os.getuid()}"
    )
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    return folder


def socket_path(config: LabnotesConfig, name: str) -> Path:
    """Return the version-keyed bind path outside the experiment tree."""
    return runtime_folder() / f"{daemon_key(config, name)}.sock"


def discovery_folder(config: LabnotesConfig, name: str) -> Path:
    """Find daemon metadata alongside the experiment's run journals."""
    return journal_folder(runs_parent(config.root, config.runs, name))


def socket_record(config: LabnotesConfig, name: str) -> Path:
    """Point clients to the current socket without guessing runtime settings."""
    return discovery_folder(config, name) / f"{daemon_key(config, name)}.socket"


def lock_path(config: LabnotesConfig, name: str) -> Path:
    """Serialize one daemon per experiment and package version."""
    return discovery_folder(config, name) / f"{daemon_key(config, name)}.lock"
