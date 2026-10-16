import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path

from labnotes.list_experiments import list_experiments


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="labnotes")
    parser.add_argument("--version", action="version", version=version("labnotes"))
    parser.add_argument(
        "--experiments-folder",
        type=Path,
        required=True,
        help="one subfolder per experiment, each with a design.yaml and markdown notes",
    )
    parser.add_argument(
        "--data-folder",
        type=Path,
        required=True,
        help="run data, with a .dirsql.toml declaring a runs table that has a study column",
    )
    args = parser.parse_args(argv)
    experiments = asyncio.run(
        list_experiments(args.experiments_folder, args.data_folder)
    )
    print(json.dumps(experiments, indent=2))
