from collections.abc import Sequence

from rich.text import Text


def startup_steps(steps: Sequence[str], spinner: str) -> Text:
    """List finished steps, then the current one spinning."""
    shown = Text()
    for index, step in enumerate(steps):
        done = index < len(steps) - 1
        shown.append(f"{'✓' if done else spinner} {step}\n")
    return shown
