from collections.abc import Sequence

from rich.text import Text


def startup_steps(steps: Sequence[str], spinner: str) -> Text:
    """List finished steps, then the current one spinning."""
    if not steps:
        return Text()
    lines = [f"✓ {step}\n" for step in steps[:-1]]
    return Text("".join(lines) + f"{spinner} {steps[-1]}\n")
