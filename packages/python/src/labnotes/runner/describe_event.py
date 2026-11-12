from labnotes.retries import RETRY_EXIT_CODE
from labnotes.runner.param_args import param_args
from labnotes.tui.format_elapsed import format_elapsed


def describe_event(event: dict[str, object]) -> str:
    match event["event"]:
        case "planned":
            runs = len(event["runs"])  # type: ignore[arg-type]
            if not runs:
                return "Nothing to run: every combination has its repeats."
            return f"{runs} runs to go, {event['concurrency']} at a time."
        case "started":
            args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
            return f"{event['run']} started {args}".rstrip()
        case "ended":
            outcome = event["error"] or f"exited {event['exit_code']}"
            return f"{event['run']} {outcome}"
        case "stopping run":
            return f"Stopping {event['run']}."
        case "killing run":
            return f"Killing {event['run']}."
        case "held":
            return f"{event['run']} held by another run."
        case "retried" if event["retry"] == event["run"]:
            return f"{event['run']} retried in its folder."
        case "retried":
            return f"{event['run']} retried as {event['retry']}."
        case "retrying":
            wait = format_elapsed(event["seconds"])  # type: ignore[arg-type]
            attempt = f"{event['attempt']} of {event['retries']}"
            return f"{event['run']} retries in {wait} (retry {attempt})."
        case "gave up":
            tried = f"after {event['retries']} retries"
            code = event.get("exit_code", RETRY_EXIT_CODE)
            return f"{event['run']} gave up (exit {code}) {tried}."
        case "capped":
            cells = len(event["runs"])  # type: ignore[arg-type]
            noun = "cell" if cells == 1 else "cells"
            return f"{cells} {noun} gave up after {event['retries']} retries."
        case "retry cancelled":
            return f"{event['run']} won't retry."
        case "idle":
            return "No runs left."
        case "concurrency":
            return f"{event['concurrency']} at a time."
        case "setting up":
            return "Setting up."
        case "tearing down":
            return "Tearing down."
        case "hook ended" if event["error"]:
            return str(event["error"])
        case "hook ended":
            return f"{str(event['hook']).capitalize()} finished."
        case "teardown failed":
            return str(event["error"])
        case "daemon error":
            return str(event["error"])
        case "stopping":
            return "Stopping runs. Ctrl-C again to kill them."
        case "finishing up":
            return "Finishing up. Queued runs won't start; running cells will finish."
        case _:
            return "Killing runs."
