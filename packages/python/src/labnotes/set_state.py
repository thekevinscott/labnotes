import json

from labnotes.get_state import get_state
from labnotes.state_path import state_path


def set_state(values: dict[str, object]) -> None:
    """Merge setup's JSON state by key for this invocation's teardown."""
    path = state_path(writable=True)
    content = json.dumps({**get_state(), **values})
    path.write_text(content, encoding="utf-8")
