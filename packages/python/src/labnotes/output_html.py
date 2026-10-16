import re
from collections.abc import Mapping, Sequence
from html import escape

from labnotes.data_html import data_html

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def output_html(outputs: Sequence[Mapping[str, object]]) -> str:
    parts = []
    for output in outputs:
        kind = output["msg_type"]
        content = output["content"]
        assert isinstance(content, Mapping)
        if kind == "stream":
            parts.append(
                f'<pre class="{escape(content["name"])}">{escape(content["text"])}</pre>'
            )
        elif kind in ("execute_result", "display_data"):
            parts.append(data_html(content["data"]))
        elif kind == "error":
            trace = ANSI.sub("", "\n".join(content["traceback"]))
            parts.append(f'<pre class="error">{escape(trace)}</pre>')
    return "".join(parts)
