from labnotes.run_columns import run_columns
from labnotes.view.experiment import Experiment


def invocation_columns(experiment: Experiment) -> list[dict[str, str]]:
    keys = run_columns(experiment.config)
    if experiment.groups is not None:
        keys.insert(1, "runs")
    return [{"key": "status", "label": ""}, *({"key": k, "label": k} for k in keys)]
