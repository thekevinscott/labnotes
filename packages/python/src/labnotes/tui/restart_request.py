import os
from pathlib import Path


def restart_request(run_id: str, experiment_config: Path | None) -> dict[str, object]:
    return {
        "command": "restart",
        "options": {
            "run_id": run_id,
            "experiment_config": None
            if experiment_config is None
            else str(experiment_config),
            "environment": dict(os.environ),
        },
    }
