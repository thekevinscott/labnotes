import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static

from labnotes.tui.view_pane import ViewPane, failure
from labnotes.view.experiment import Experiment

EXPERIMENT = Experiment(Path("/p"), "alpha", {"alpha/runs/a": {"id": "a"}})

VIEWS = """\
from textual.widget import Widget
from textual.widgets import Static

from labnotes.view import Changed


class Shown(Static):
    def on_labnotes_changed(self, message: Changed) -> None:
        names = None if message.experiment is None else message.experiment.name
        self.update(f"{names} {sorted(message.paths)}")


class Boom(Widget):
    def compose(self):
        raise RuntimeError("compose broke")
        yield


class Late(Static):
    def on_labnotes_changed(self, message: Changed) -> None:
        raise RuntimeError("late break")


class Raising(Widget):
    def __init__(self):
        raise RuntimeError("init broke")
"""


def host(pane: ViewPane) -> App[None]:
    class Host(App[None]):
        def compose(self) -> ComposeResult:
            yield pane

    return Host()


def pane(tmp_path: Path, name: str) -> ViewPane:
    (tmp_path / "views.py").write_text(VIEWS)
    return ViewPane("plot", f"views.py:{name}", tmp_path, id="view-2")


def text(pane: ViewPane) -> str:
    return "\n".join(str(each.content) for each in pane.query(Static))


def drive(pane: ViewPane, *steps: object) -> App[None]:
    app = host(pane)

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            for step in steps:
                if callable(step):
                    step()
                await pilot.pause()

    asyncio.run(run())
    return app


def test_mounts_the_view_and_delivers_changes(tmp_path: Path) -> None:
    shown = pane(tmp_path, "Shown")
    seen: list[str] = []

    drive(
        shown,
        lambda: shown.deliver(EXPERIMENT),
        lambda: seen.append(text(shown)),
        lambda: shown.deliver(None, frozenset({"alpha/runs/a/x"})),
        lambda: seen.append(text(shown)),
    )

    assert shown.id == "view-2"
    assert shown.view_name == "plot"
    assert seen == ["alpha []", "None ['alpha/runs/a/x']"]


def test_shows_why_a_view_failed_to_load(tmp_path: Path) -> None:
    missing = pane(tmp_path, "Missing")
    seen: list[str] = []

    app = drive(missing, lambda: seen.append(text(missing)))

    assert missing.view is None
    assert seen[0].startswith("The plot view failed.\n\nTraceback")
    assert "ImportError: views.py has no Missing" in seen[0]
    assert app.return_code is None


def test_shows_why_a_view_failed_to_build(tmp_path: Path) -> None:
    raising = pane(tmp_path, "Raising")
    seen: list[str] = []

    drive(raising, lambda: seen.append(text(raising)))

    assert "RuntimeError: init broke" in seen[0]


def test_replaces_a_view_that_fails_to_compose_with_why(tmp_path: Path) -> None:
    boom = pane(tmp_path, "Boom")
    seen: list[str] = []

    app = drive(boom, lambda: seen.append(text(boom)))

    assert boom.view is None
    assert seen[0].startswith("The plot view failed.")
    assert "RuntimeError: compose broke" in seen[0]
    assert app.return_code is None


def test_replaces_a_view_that_fails_later_and_stops_delivering(tmp_path: Path) -> None:
    late = pane(tmp_path, "Late")
    seen: list[str] = []

    drive(
        late,
        lambda: late.deliver(EXPERIMENT),
        lambda: seen.append(text(late)),
        lambda: late.deliver(EXPERIMENT),
        lambda: seen.append(text(late)),
    )

    assert "RuntimeError: late break" in seen[0]
    assert seen[1] == seen[0]
    assert late.view is None


def test_shows_one_failure_when_errors_repeat(tmp_path: Path) -> None:
    late = pane(tmp_path, "Late")
    counts: list[int] = []

    def fail_twice() -> None:
        late.fail(RuntimeError("one"))
        late.fail(RuntimeError("two"))

    drive(late, fail_twice, lambda: counts.append(len(late.query(".failure"))))

    assert counts == [1]


def test_failure_is_plain_text() -> None:
    shown = failure("plot", ValueError("[bold]x[/]"))

    assert str(shown.content).endswith("ValueError: [bold]x[/]\n")
    assert shown.has_class("failure")
