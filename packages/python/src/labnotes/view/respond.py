import json
from collections.abc import Iterable
from typing import TextIO

from labnotes.view.answer import answer
from labnotes.view.build import Build


def respond(build: Build, lines: Iterable[str], out: TextIO) -> None:
    for line in lines:
        if line.strip():
            out.write(json.dumps(answer(build, json.loads(line))) + "\n")
            out.flush()
