import argparse
from importlib.metadata import version


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="labnotes")
    parser.add_argument("--version", action="version", version=version("labnotes"))
    parser.parse_args(argv)
