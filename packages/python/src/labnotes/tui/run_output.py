import codecs
from pathlib import Path

from textual.widgets import Log

STREAMS = ("stdout", "stderr")


class RunOutput(Log):
    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self.reset()

    def reset(self) -> None:
        self.offsets = dict.fromkeys(STREAMS, 0)
        self.decoders = {
            stream: codecs.getincrementaldecoder("utf-8")(errors="replace")
            for stream in STREAMS
        }
        self.last_stream: str | None = None
        self.mid_line = False
        self.clear()

    def follow(self, folder: Path) -> None:
        for stream in STREAMS:
            path = folder / f"{stream}.log"
            if not path.exists():
                continue
            with path.open("rb") as log:
                log.seek(self.offsets[stream])
                data = log.read()
            self.offsets[stream] += len(data)
            text = self.decoders[stream].decode(data)
            if not text:
                continue
            # Don't glue one stream's unfinished line onto the other's output.
            if self.mid_line and stream != self.last_stream:
                text = "\n" + text
            self.write(text)
            self.last_stream = stream
            self.mid_line = not text.endswith("\n")
