import posixpath


def experiment_toml(template: str) -> str:
    return posixpath.join(template, "experiment.toml")
