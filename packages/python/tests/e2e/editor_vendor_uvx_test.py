import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def test_installed_server_serves_editor_vendor(
    tmp_path: Path, uvx: dict[str, str]
) -> None:
    config = tmp_path / ".labnotes.toml"
    config.write_text("", encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        ["uvx", "labnotes", "-c", str(config), "server", "-p", str(port)],
        env={**os.environ, **uvx},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}/static/vendor/module-5.js"
        for _ in range(100):
            try:
                with urlopen(url, timeout=1) as response:
                    assert response.status == 200
                    assert b"EditorState" in response.read()
                    break
            except URLError:
                if process.poll() is not None:
                    raise AssertionError(
                        "Installed server exited before serving editor module"
                    )
                time.sleep(0.1)
        else:
            raise AssertionError("Installed server did not serve editor module")
    finally:
        process.terminate()
        process.wait(timeout=10)
