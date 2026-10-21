def stopped_title(title: str | None, error: BaseException | None) -> str:
    reason = f"Live updates stopped: {error}" if error else "Live updates stopped."
    return f"{title} · {reason}" if title else reason
