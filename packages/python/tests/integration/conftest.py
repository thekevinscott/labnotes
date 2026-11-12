import asyncio
import json
import socket
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.async_api import Page, async_playwright


CONFIG = (
    'name = "Alpha study"\ncontinues = false\ncommand = "go"\nrepeats = 2\n'
    '[params]\nsource-language = ["en", "fr"]\n'
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(project: Path, name: str, params: dict[str, object], **fields: object) -> None:
    record = {"params": params, "created": f"2026-10-17T00:00:0{name[-1]}Z", **fields}
    write(project / f"alpha/runs/{name}/run.json", json.dumps(record))


def project(root: Path) -> Path:
    write(root / "beta/files/notes.md", "beta notes")
    write(root / ".labnotes.toml", "")
    write(root / "alpha/experiment.toml", CONFIG)
    write(root / "alpha/files/plan.md", "# The plan\n\n```python\n1 + 1\n```\n")
    write(root / "alpha/files/results.md", "# Results\n\nAll good.\n")
    run(root, "run1", {"source-language": "en"}, exit_code=0)
    run(root, "run2", {"source-language": "fr"}, exit_code=1, stdout="boom")
    return root


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve(root: Path) -> Iterator[str]:
    port = free_port()
    labnotes = Path(sys.executable).parent / "labnotes"
    process = subprocess.Popen(
        [labnotes, "-c", root / ".labnotes.toml", "server", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port)).close()
                break
            except OSError:
                time.sleep(0.1)
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait()


def browse(
    url: str,
    check: Callable[[Page], Awaitable[None]],
    width: int = 1280,
    timezone_id: str = "UTC",
) -> None:
    async def drive() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(
                viewport={"width": width, "height": 800}, timezone_id=timezone_id
            )
            # pytest shows these only when a test fails (#307).
            page.on(
                "requestfailed",
                lambda r: print("request failed:", r.url, r.failure),
            )
            page.on(
                "response",
                lambda r: print("response:", r.status, r.url)
                if r.status >= 400
                else None,
            )
            page.on(
                "console",
                lambda m: print("console:", m.type, m.text)
                if m.type == "error"
                else None,
            )
            external_request: asyncio.Future[str] = (
                asyncio.get_running_loop().create_future()
            )

            async def block_external(route) -> None:
                hostname = urlparse(route.request.url).hostname
                if hostname not in {"127.0.0.1", "localhost", "::1"}:
                    if not external_request.done():
                        external_request.set_result(route.request.url)
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_external)
            await page.goto(url)
            try:
                if external_request.done():
                    raise AssertionError(
                        f"Non-local browser request: {external_request.result()}"
                    )
                check_task = asyncio.create_task(check(page))
                done, _ = await asyncio.wait(
                    [check_task, external_request], return_when=asyncio.FIRST_COMPLETED
                )
                if external_request in done:
                    check_task.cancel()
                    raise AssertionError(
                        f"Non-local browser request: {external_request.result()}"
                    )
                await check_task
            finally:
                await browser.close()

    asyncio.run(drive())


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    # Real project roots run long; pytest's short default hides path-length
    # limits such as the 107-byte AF_UNIX socket path.
    deep = (
        tmp_path
        / "a-fairly-long-folder-name-for-research"
        / "and-another-nested-one"
        / "experiments-and-their-notes-live-here"
    )
    deep.mkdir(parents=True)
    return deep


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    yield from serve(project(tmp_path))


def run_tui_command(
    root: Path, argv: list[str], timeout: float = 120, env: dict[str, str] | None = None
) -> int:
    """Drive a completed experiment through the real CLI and TUI in a PTY."""
    import re
    import shlex

    from curtaincall import Terminal

    executable = Path(sys.executable).parent / "labnotes"
    command = shlex.join([str(executable), "-c", str(root / ".labnotes.toml"), *argv])
    term = Terminal(
        "/bin/sh -c " + shlex.quote(f"cd {shlex.quote(str(root))} && exec {command}"),
        rows=30,
        cols=300,
        env=env,
    )
    term.start()
    summary = re.compile(r"\d+ passed, \d+ failed\.(?: \d+ retried\.)?")
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            screen = term._get_screen_text()
            found = summary.search(screen)
            if found:
                term.key_ctrl_c()
                code = term.wait(timeout=10)
                term._drain_output()
                print(screen.strip())
                print(term._get_screen_text().strip())
                print(found.group())
                return code
            if not term.is_alive:
                code = term.wait(timeout=2)
                term._drain_output()
                print(term._get_screen_text().strip(), file=sys.stderr)
                return code
            time.sleep(0.05)
        raise TimeoutError(
            f"TUI did not finish within {timeout}s: {term.to_snapshot()}"
        )
    finally:
        term.kill()


def daemon_request(
    path: Path, method: str, route: str, body: object = None, timeout: float = 30
) -> dict[str, object]:
    """Send one HTTP request over a daemon socket; a start's reply is its last event."""
    import httpx2

    with httpx2.Client(
        transport=httpx2.HTTPTransport(uds=str(path)),
        base_url="http://labnotes",
        timeout=timeout,
    ) as client:
        response = client.request(method, route, json=body)
        if response.headers["content-type"].startswith("text/event-stream"):
            events = [
                line.removeprefix("data: ")
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            return json.loads(events[-1])  # type: ignore[no-any-return]
        return response.json()  # type: ignore[no-any-return]


class DaemonEvents:
    """One open GET /events stream, read event by event."""

    def __init__(self, path: Path, timeout: float = 10) -> None:
        import httpx2

        self.client = httpx2.Client(
            transport=httpx2.HTTPTransport(uds=str(path)),
            base_url="http://labnotes",
            timeout=timeout,
        )
        self.response = self.client.send(
            self.client.build_request("GET", "/events"), stream=True
        )
        assert self.response.status_code == 200, self.response.read()
        self.events = iter(httpx2.EventSource(self.response))
        first = next(self.events)
        assert first.event == "batches", first
        self.batches: list[str] = first.json()["batches"]

    def next(self) -> dict[str, object]:
        import httpx2

        try:
            event = next(self.events)
        except httpx2.ReadTimeout:
            raise AssertionError("daemon streamed nothing to the attached client")
        except StopIteration:
            raise AssertionError("daemon closed the event stream")
        return event.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        self.response.close()
        self.client.close()

    def __enter__(self) -> "DaemonEvents":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
