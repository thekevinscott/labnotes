from collections.abc import Callable
from typing import Any

type Row = dict[str, Any]
type Build = Callable[[list[Any]], tuple[list[Any], Callable[[Row], Row]]]
