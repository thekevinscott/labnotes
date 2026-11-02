from labnotes.view.experiment import Experiment


def invocation_columns(experiment: Experiment) -> list[dict[str, str]]:
    keys = list(experiment.columns)
    if experiment.groups is not None:
        keys.insert(1, "runs")
    return [{"key": "status", "label": ""}, *({"key": k, "label": k} for k in keys)]
