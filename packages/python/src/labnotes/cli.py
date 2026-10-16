import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path

import uvicorn

from labnotes.create_app import create_app
from labnotes.dump_experiments import dump_experiments


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="labnotes", description="Browse experiments and their run data."
    )
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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--json",
        action="store_true",
        help="print experiments as JSON instead of serving",
    )
    args = parser.parse_args(argv)
    if args.json:
        experiments = asyncio.run(
            dump_experiments(args.experiments_folder, args.data_folder)
        )
        print(json.dumps(experiments, indent=2))
        return
    print(f"labnotes at http://{args.host}:{args.port}", flush=True)
    uvicorn.run(
        create_app(args.experiments_folder, args.data_folder),
        host=args.host,
        port=args.port,
        log_level="warning",
    )
