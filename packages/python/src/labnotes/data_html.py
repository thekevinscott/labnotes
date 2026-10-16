from collections.abc import Mapping
from html import escape


def data_html(data: Mapping[str, str]) -> str:
    # Rich output is trusted: it comes from code in the user's own notes.
    for mime in ("text/html", "image/svg+xml"):
        if mime in data:
            return data[mime]
    if "image/png" in data:
        return f'<img alt="" src="data:image/png;base64,{data["image/png"]}">'
    return f"<pre>{escape(data.get('text/plain', ''))}</pre>"
