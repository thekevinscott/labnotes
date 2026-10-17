from importlib.metadata import version
from importlib.resources import files


def context_guide() -> str:
    guide = files("labnotes").joinpath("context.md").read_text(encoding="utf-8")
    return f"labnotes {version('labnotes')}\n\n{guide}"
