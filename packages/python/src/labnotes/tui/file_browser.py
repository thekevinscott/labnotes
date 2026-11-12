from bisect import bisect
from pathlib import Path, PurePosixPath

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from labnotes.tui.file_tail import FileTail
from labnotes.view.changed import Changed
from labnotes.view.experiment import Experiment


class FileBrowser(Horizontal):
    """List each run's files and tail the one you select."""

    DEFAULT_CSS = """
    FileBrowser { height: 1fr; }
    FileBrowser Tree { width: 40; }
    FileBrowser FileTail { width: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.project = Path()
        self.runs: dict[str, TreeNode[str | None]] = {}
        self.files: dict[str, TreeNode[str | None]] = {}
        self.tailing: str | None = None
        self.synced: Experiment | None = None

    def compose(self) -> ComposeResult:
        tree: Tree[str | None] = Tree("runs")
        tree.show_root = False
        yield tree
        yield FileTail()

    def on_labnotes_changed(self, message: Changed) -> None:
        if message.experiment is not self.synced:
            self.synced = message.experiment
            self.sync(message.experiment)
        if self.tailing in message.paths:
            self.query_one(FileTail).follow()

    def sync(self, experiment: Experiment | None) -> None:
        runs = (
            {} if experiment is None else {str(r["folder"]): r for r in experiment.runs}
        )
        listed: dict[str, str] = {}
        for path in () if experiment is None else experiment.files:
            folder = next(
                (str(p) for p in PurePosixPath(path).parents if str(p) in runs), None
            )
            if folder is not None:
                listed[path] = folder
        for path in self.files.keys() - listed.keys():
            self.files.pop(path).remove()
        for folder in self.runs.keys() - runs.keys():
            self.runs.pop(folder).remove()
        tree = self.query_one(Tree)
        for folder, run in runs.items():
            if folder not in self.runs:
                self.runs[folder] = tree.root.add(str(run["id"]), expand=True)
        for path, folder in listed.items():
            if path not in self.files:
                node = self.runs[folder]
                name = path.removeprefix(f"{folder}/")
                self.files[path] = node.add_leaf(
                    name, path, before=self.place(node, name)
                )
        if experiment is not None:
            self.project = experiment.root

    def place(self, node: TreeNode[str | None], name: str) -> int:
        children = node.children
        # Files mostly arrive in order; skip the scan for those.
        if not children or str(children[-1].label) <= name:
            return len(children)
        return bisect([str(leaf.label) for leaf in children], name)

    def on_tree_node_selected(self, event: Tree.NodeSelected[str | None]) -> None:
        if event.node.data is not None:
            self.tailing = event.node.data
            self.query_one(FileTail).open(self.project / self.tailing)
