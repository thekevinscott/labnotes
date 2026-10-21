from labnotes.read_path import DEFAULT_PATHS, SINGLE_PATHS


def default_config_text(*, single: bool = False) -> str:
    paths = SINGLE_PATHS if single else DEFAULT_PATHS
    return "\n".join(
        f'[{table}]\npath = "{template}"\n'
        for table, template in paths.items()
        if template
    )
