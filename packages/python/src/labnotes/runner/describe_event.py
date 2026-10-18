from labnotes.runner.param_args import param_args


def describe_event(event: dict[str, object]) -> str:
    match event["event"]:
        case "planned":
            runs = len(event["runs"])  # type: ignore[arg-type]
            return f"{runs} runs to go, {event['concurrency']} at a time."
        case "started":
            args = " ".join(param_args(event["params"]))  # type: ignore[arg-type]
            return f"{event['run']} started {args}".rstrip()
        case "ended":
            outcome = event["error"] or f"exited {event['exit_code']}"
            return f"{event['run']} {outcome}"
        case "queued":
            return f"{event['run']} runs next."
        case "stopping":
            return "Stopping runs. Ctrl-C again to kill them."
        case _:
            return "Killing runs."
