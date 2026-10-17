from labnotes.read_path import DEFAULT_PATHS


def default_config_text() -> str:
    return "\n".join(
        f'[{table}]\npath = "{template}"\n' for table, template in DEFAULT_PATHS.items()
    )
