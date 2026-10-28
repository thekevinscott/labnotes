import json

from labnotes.state_path import state_path


def get_state() -> dict[str, object]:
    """Read invocation state so teardown can clean up what setup created."""
    path = state_path()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(state, dict):
        raise ValueError("Invocation state must be a JSON object")
    return state
