from markupsafe import Markup, escape


def format_started(utc: str | None) -> Markup:
    if utc is None:
        return Markup("—")
    stamp = escape(utc)
    return Markup(f'<time datetime="{stamp.replace(" ", "T")}Z">{stamp}</time>')
