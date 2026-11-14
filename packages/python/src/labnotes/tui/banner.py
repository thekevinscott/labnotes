class Banner:
    def __init__(self, label: str) -> None:
        self.label = label
        self.lines = 1
        self.rows = 1

    def read(self, first: int, count: int) -> list[bytes]:
        if first or not count:
            return []
        return [f"\x1b[2m── {self.label} ──\x1b[0m".encode()]
