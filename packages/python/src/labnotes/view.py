import json
import sys
from collections.abc import Callable, Iterable
from typing import Any, TextIO

type Row = dict[str, Any]
type Build = Callable[[list[Any]], tuple[list[Any], Callable[[Row], Row]]]


def answer(build: Build, request: dict[str, Any]) -> dict[str, Any]:
    columns, row = build(request["columns"])
    return {
        "columns": columns,
        "rows": {folder: row(native) for folder, native in request["rows"].items()},
    }


def respond(build: Build, lines: Iterable[str], out: TextIO) -> None:
    for line in lines:
        if line.strip():
            out.write(json.dumps(answer(build, json.loads(line))) + "\n")
            out.flush()


def serve[F: Build](build: F) -> F:
    """Answer labnotes' runs-table requests with the decorated function.

    Scripts import this, so the module stays standard-library only. It serves
    only from the script labnotes runs, so tests can import the function.
    """
    if build.__module__ != "__main__":
        return build
    # stdout carries the protocol, so stray prints go to stderr.
    out, sys.stdout = sys.stdout, sys.stderr
    try:
        respond(build, sys.stdin, out)
    finally:
        sys.stdout = out
    return build
