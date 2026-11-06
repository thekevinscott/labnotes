from collections.abc import Sequence

from rich.text import Text

MARKS = {"waiting": ("○", "dim"), "passed": ("✓", ""), "failed": ("✗", "red")}


def stage_line(stages: Sequence[tuple[str, str]], current: str, spinner: str) -> Text:
    line = Text()
    for index, (stage, state) in enumerate(stages):
        if index:
            line.append("  ›  ", style="dim")
        mark, style = MARKS.get(state, (spinner, ""))
        if stage == current:
            style = f"{style} bold reverse".strip()
        line.append(f" {stage} {mark} ", style=style)
    return line
