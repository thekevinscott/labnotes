from textual.message import Message

from typing import TYPE_CHECKING

from labnotes.view.experiment import Experiment

if TYPE_CHECKING:
    from labnotes.view.daemon import Daemon


class Changed(Message, bubble=False, namespace="labnotes"):
    """Tell a view its experiment changed. Handle it as `on_labnotes_changed`.

    `experiment` is None once the experiment is removed. `paths` names the run
    files that changed, relative to the project root; it is empty when runs or
    config changed instead. `daemon` reads the experiment's daemon routes.
    """

    def __init__(
        self,
        experiment: Experiment | None,
        paths: frozenset[str] = frozenset(),
        daemon: "Daemon | None" = None,
    ) -> None:
        super().__init__()
        self.experiment = experiment
        self.paths = paths
        self.daemon = daemon
