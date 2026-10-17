from labnotes.runner.param_args import param_args


def test_passes_each_param_as_a_flag() -> None:
    assert param_args(
        {"model": "opus", "n": 2, "t": 0.5, "on": True, "off": False, "l": [1], "d": {"k": "v"}}
    ) == [
        "--model", "opus",
        "--n", "2",
        "--t", "0.5",
        "--on", "1",
        "--off", "0",
        "--l", "[1]",
        "--d", '{"k": "v"}',
    ]  # fmt: skip


def test_dashes_underscored_names() -> None:
    assert param_args({"source_language": "python"}) == ["--source-language", "python"]
