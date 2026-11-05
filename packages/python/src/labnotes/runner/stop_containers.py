import shutil

from labnotes.runner.container_memory import LABEL
from labnotes.runner.docker_output import docker_output


def stop_containers(run_id: str) -> None:
    """Stop Docker containers that outlive their run's host process tree."""
    if shutil.which("docker") is None:
        return
    ids = docker_output(
        "ps", "--quiet", "--no-trunc", "--filter", f"label={LABEL}={run_id}"
    )
    if ids is None:
        return
    for container_id in ids.splitlines():
        docker_output("kill", container_id)
