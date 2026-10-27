import subprocess


def docker_output(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None
