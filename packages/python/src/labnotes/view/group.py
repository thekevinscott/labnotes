from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Group:
    """Name one invocation and the folders of its runs, in run order.

    `flat` is true for a run that ran on its own rather than nested.
    """

    name: str
    folders: tuple[str, ...]
    flat: bool
