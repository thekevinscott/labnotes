import sys

from labnotes.view.build import Build
from labnotes.view.respond import respond


def serve[F: Build](build: F) -> F:
    """Answer labnotes' runs-table requests with the decorated function.

    Scripts import this, so the package stays standard-library only. It serves
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
