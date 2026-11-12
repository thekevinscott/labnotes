from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import pytest

from labnotes.experiments import experiments


@pytest.fixture
def collaborators() -> Iterator[dict[str, mock.MagicMock]]:
    with mock.patch("labnotes.experiments.load_config") as load_config:
        yield {"load_config": load_config}


def run(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exit_info:
        experiments.main(argv, prog_name="experiments")
    return exit_info.value.code


@pytest.mark.parametrize("argv", [[], ["a"]])
def test_a_bare_command_names_the_actions(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(argv) == 2

    assert "action: run, attach or stop." in capsys.readouterr().err


def test_needs_a_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    collaborators["load_config"].return_value = None

    assert run([]) == 1

    assert "No .labnotes.toml here. Run labnotes init" in capsys.readouterr().err


def test_stop_sends_command_and_reports_missing_daemon(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch(
        "labnotes.experiments.daemon_command", return_value={"ok": True}
    ) as send:
        assert run(["a", "stop"]) == 0
    send.assert_called_once_with(
        collaborators["load_config"].return_value, "a", {"command": "stop_all"}
    )
    assert "stop all runs" in capsys.readouterr().out
    with mock.patch(
        "labnotes.experiments.daemon_command",
        side_effect=ValueError("No daemon is running"),
    ):
        assert run(["a", "stop"]) == 1
    assert "No daemon" in capsys.readouterr().err
    with mock.patch(
        "labnotes.experiments.daemon_command",
        return_value={"ok": False, "error": "command failed"},
    ):
        assert run(["a", "stop"]) == 1
    assert "command failed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "option",
    [
        ["--concurrency", "2"],
        ["--run-id", "r"],
        ["--timeout", "3"],
        ["--setup", "echo ok"],
        ["--teardown", "echo ok"],
        ["--retries", "2"],
        ["--retry-wait", "1"],
        ["--replace-capped"],
        ["--", "arg"],
        ["--model=x"],
    ],
)
@pytest.mark.parametrize("action", ["stop", "attach"])
def test_stop_and_attach_reject_run_options(
    action: str,
    option: list[str],
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", action, *option]) == 2
    assert f"{action} takes no run options" in capsys.readouterr().err


def test_stop_rejects_an_experiment_config_option(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    path = tmp_path / "other.toml"
    path.touch()
    assert run(["a", "stop", "-e", str(path)]) == 2
    assert "stop takes no run options" in capsys.readouterr().err


@pytest.mark.parametrize("action", ["jump", "zap", "runs"])
def test_rejects_an_unknown_action(
    action: str,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", action]) == 2

    assert (
        f"Unknown action {action}. Use run, attach or stop." in capsys.readouterr().err
    )


def test_needs_run_for_params(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["a", "jump", "--model=small", "--lang=en"]) == 2

    assert "Unexpected --model=small. --PARAM=VALUE needs run." in (
        capsys.readouterr().err
    )


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["a", "jump", "--run-id", "r1"], "--run-id needs run"),
        (["a", "jump", "--retries", "2"], "--retries needs run"),
        (["a", "jump", "--retry-wait", "1"], "--retry-wait needs run"),
        (["a", "jump", "--replace-capped"], "--replace-capped needs run"),
        (
            ["a", "run", "--run-id", "r1", "--model=small"],
            "--run-id uses the run's recorded params",
        ),
        (
            ["a", "run", "--run-id", "r1", "--", "--token"],
            "--run-id uses the run's recorded params",
        ),
    ],
)
def test_run_id_rejects_conflicting_inputs(
    argv: list[str],
    expected: str,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
) -> None:
    assert run(argv) == 2
    assert expected in capsys.readouterr().err


@pytest.fixture
def drivers() -> Iterator[dict[str, mock.MagicMock]]:
    results = [{"exit_code": 0}, {"exit_code": 0}]
    with (
        mock.patch("labnotes.experiments.run_tui", return_value=results) as run_tui,
        mock.patch("labnotes.experiments.sys") as sys,
        mock.patch("labnotes.experiments.os", mock.Mock(environ={"KEY": "value"})),
        mock.patch(
            "labnotes.experiments.parse_subset", return_value={}
        ) as parse_subset,
    ):
        sys.stdout.isatty.return_value = True
        sys.stderr.isatty.return_value = True
        yield {
            "run_tui": run_tui,
            "sys": sys,
            "parse_subset": parse_subset,
        }


def test_runs_an_experiment_through_daemon(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--concurrency", "3"]) == 0
    options = drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]
    assert options["concurrency"] == 3
    drivers["run_tui"].assert_called_once()


def test_runs_an_experiment_from_a_named_config(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    path = tmp_path / "other.toml"
    path.touch()

    assert run(["a", "run", "-e", str(path)]) == 0

    assert drivers["run_tui"].call_args.kwargs["daemon_request"]["options"][
        "experiment_config"
    ] == str(path)


def test_resolves_named_config_from_the_invoking_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    (tmp_path / "alt").mkdir()
    path = tmp_path / "alt/experiment.toml"
    path.touch()
    monkeypatch.chdir(tmp_path)

    assert run(["a", "run", "-e", "alt/experiment.toml"]) == 0

    options = drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]
    assert options["experiment_config"] == str(path)


def test_passes_the_setup_and_teardown_flags(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--setup", "up", "--teardown", "down"]) == 0

    assert (
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["setup"],
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["teardown"],
    ) == ("up", "down")


def test_passes_the_labnotes_command_line(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    ctx = experiments.make_context("experiments", ["a", "run"])
    ctx.meta["labnotes.command_line"] = "labnotes experiments a run"

    with ctx:
        experiments.invoke(ctx)

    assert drivers["run_tui"].call_args.kwargs["daemon_request"]["options"][
        "command_line"
    ] == ("labnotes experiments a run")


def test_runs_the_subset_given_as_params(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--model=small", "--timeout", "5", "--lang=en"]) == 0

    drivers["parse_subset"].assert_called_once_with(["--model=small", "--lang=en"])
    options = drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]
    assert options["only"] == drivers["parse_subset"].return_value
    assert options["timeout"] == 5


def test_passes_args_after_the_double_dash_through(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    argv = ["a", "run", "--model=small", "--", "--auth", "api", "--", "x"]

    assert run(argv) == 0

    drivers["parse_subset"].assert_called_once_with(["--model=small"])
    assert drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["args"] == [
        "--auth",
        "api",
        "--",
        "x",
    ]


def test_sends_no_args_for_a_bare_double_dash(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--"]) == 0

    assert (
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["args"] is None
    )


@pytest.mark.parametrize("argv", [["a", "--", "--auth"], ["a", "jump", "--"]])
def test_rejects_args_without_run(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(argv) == 2

    assert "Error: -- ARGS needs run." in capsys.readouterr().err


def test_rejects_a_malformed_param(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["parse_subset"].side_effect = ValueError("Unexpected --model.")

    assert run(["a", "run", "--model"]) == 2

    assert "Error: Unexpected --model." in capsys.readouterr().err


def test_help_says_params_pick_a_subset(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    help_text = " ".join(capsys.readouterr().out.split())
    assert "With run, --PARAM=VALUE runs only the matrix cells where that param" in (
        help_text
    )
    assert "anything after -- is appended to every run's command" in help_text
    assert "(repeat it for several values)" in help_text


def test_reports_an_experiment_that_cannot_run(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["run_tui"].side_effect = ValueError("a is already running")

    assert run(["a", "run"]) == 1

    assert "a is already running" in capsys.readouterr().err


def test_help_says_concurrency_falls_back_to_config(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    assert "1 if none" in capsys.readouterr().out


def test_needs_a_concurrency_of_at_least_one(
    collaborators: dict[str, mock.MagicMock], drivers: dict[str, mock.MagicMock]
) -> None:
    assert run(["a", "run", "--concurrency", "0"]) == 2


@pytest.mark.parametrize("path", ["missing.toml", "."])
def test_needs_an_experiment_config_file(
    tmp_path: Path,
    path: str,
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "-e", str(tmp_path / path)]) == 2


def test_shows_the_live_view_in_a_terminal(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = True

    assert run(["a", "run", "--concurrency", "3"]) == 0

    drivers["run_tui"].assert_called_once_with(
        None,
        "a",
        collaborators["load_config"].return_value,
        None,
        daemon_request=mock.ANY,
    )
    assert drivers["run_tui"].call_args.kwargs["daemon_request"]["command"] == "start"
    assert capsys.readouterr().out == ""


def test_terminal_restart_sends_options_to_daemon(
    tmp_path: Path,
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    alternate = tmp_path / "alternate.toml"
    alternate.write_text("command = 'true'\n")
    drivers["sys"].stdout.isatty.return_value = True
    assert run(["a", "run", "--run-id", "failed", "-e", str(alternate)]) == 0
    assert drivers["run_tui"].call_args.kwargs["daemon_request"] == (
        {
            "command": "restart",
            "options": {
                "experiment_config": str(alternate),
                "concurrency": None,
                "timeout": None,
                "only": {},
                "args": None,
                "setup": None,
                "teardown": None,
                "command_line": None,
                "run_id": "failed",
                "retries": None,
                "retry_wait": None,
                "replace_capped": False,
                "environment": {"KEY": "value"},
            },
        }
    )


def test_terminal_reports_daemon_rejection(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = True
    drivers["run_tui"].side_effect = ValueError("bad config")
    assert run(["a", "run"]) == 1
    assert "bad config" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "name"), [(["new"], None), (["new", "study"], "study")]
)
def test_creates_an_experiment(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    argv: list[str],
    name: str | None,
) -> None:
    with mock.patch(
        "labnotes.experiments.create_experiment", return_value=Path("notes/study")
    ) as create_experiment:
        assert run(argv) == 0

    create_experiment.assert_called_once_with(
        collaborators["load_config"].return_value, name, None, None, None, {}
    )
    assert capsys.readouterr().out == "Created notes/study/experiment.toml\n"


def test_creates_an_experiment_from_flags(
    collaborators: dict[str, mock.MagicMock],
) -> None:
    with mock.patch(
        "labnotes.experiments.create_experiment", return_value=Path("notes/b")
    ) as create_experiment:
        # Built at runtime like argv, so an identity check can't pass.
        new = "".join(["ne", "w"])
        argv = [new, "b", "--from", "a", "--command", "go", "--repeats", "3"]
        assert run([*argv, "--param", "m=x", "--param", "m=2"]) == 0

    create_experiment.assert_called_once_with(
        collaborators["load_config"].return_value, "b", "a", "go", 3, {"m": ["x", 2]}
    )


def test_takes_one_repeat(collaborators: dict[str, mock.MagicMock]) -> None:
    with mock.patch(
        "labnotes.experiments.create_experiment", return_value=Path("notes/b")
    ) as create_experiment:
        assert run(["new", "b", "--repeats", "1"]) == 0

    assert create_experiment.call_args.args[4] == 1


def test_reports_a_bad_param(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch("labnotes.experiments.create_experiment") as create_experiment:
        assert run(["new", "b", "--param", "m"]) == 1

    assert "--param m must look like NAME=VALUE" in capsys.readouterr().err
    create_experiment.assert_not_called()


@pytest.mark.parametrize(
    ("flags", "flag"),
    [
        (["--command", "go"], "--command"),
        (["--param", "m=x"], "--param"),
        (["--repeats", "2"], "--repeats"),
        (["--from", "a"], "--from"),
    ],
)
@pytest.mark.parametrize("argv", [["a"], ["a", "run"], []])
def test_new_flags_need_new(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    argv: list[str],
    flags: list[str],
    flag: str,
) -> None:
    assert run([*argv, *flags]) == 2

    assert f"{flag} needs new." in capsys.readouterr().err


@pytest.mark.parametrize("given", ["0", "x"])
def test_needs_repeats_over_zero(
    given: str, collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch("labnotes.experiments.create_experiment") as create_experiment:
        assert run(["new", "b", "--repeats", given]) == 2

    create_experiment.assert_not_called()


def test_reports_an_experiment_that_cannot_be_created(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    with mock.patch(
        "labnotes.experiments.create_experiment",
        side_effect=ValueError("study already exists"),
    ):
        assert run(["new", "study"]) == 1

    assert "study already exists" in capsys.readouterr().err


def test_sends_the_timeout_in_seconds(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--timeout", "90"]) == 0

    assert (
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["timeout"]
        == 90
    )


@pytest.mark.parametrize("given", ["0", "-5"])
def test_needs_a_timeout_over_zero(
    given: str,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--timeout", given]) == 2

    assert "is not in the range x>=1" in capsys.readouterr().err


def test_help_says_runs_have_no_timeout_by_default(
    capsys: pytest.CaptureFixture[str], collaborators: dict[str, mock.MagicMock]
) -> None:
    assert run(["--help"]) == 0

    out = " ".join(capsys.readouterr().out.split())
    assert "--timeout SECONDS" in out
    assert "stop any run still going after this many seconds." in out
    assert "Unset, runs have no time limit." in out


def test_passes_retries_and_replace_capped_to_the_run(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--retries", "0", "--replace-capped"]) == 0

    assert (
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["retries"],
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["retry_wait"],
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"][
            "replace_capped"
        ],
    ) == (0, None, True)


def test_passes_retry_wait_to_the_run(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--retry-wait", "0.5"]) == 0

    assert (
        drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]["retry_wait"]
        == 0.5
    )


def test_terminal_run_sends_retry_wait_to_daemon(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = True
    assert run(["a", "run", "--retry-wait", "2"]) == 0

    options = drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]
    assert options["retry_wait"] == 2.0


def test_rejects_a_negative_retry_wait(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--retry-wait", "-1"]) == 2


def test_terminal_run_sends_retries_and_replace_capped_to_daemon(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = True
    assert run(["a", "run", "--retries", "1", "--replace-capped"]) == 0

    options = drivers["run_tui"].call_args.kwargs["daemon_request"]["options"]
    assert (options["retries"], options["replace_capped"]) == (1, True)


def test_rejects_negative_retries(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    assert run(["a", "run", "--retries", "-1"]) == 2


def test_run_without_a_terminal_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
) -> None:
    drivers["sys"].stdout.isatty.return_value = False
    assert run(["a", "run"]) == 2
    assert "requires a terminal" in capsys.readouterr().err
    drivers["run_tui"].assert_not_called()


@pytest.fixture
def batches() -> Iterator[mock.MagicMock]:
    with mock.patch("labnotes.experiments.daemon_command") as command:
        command.return_value = {"ok": True, "batches": ["b1"]}
        yield command


def test_attach_opens_the_tui_on_what_the_daemon_runs(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    batches: mock.MagicMock,
) -> None:
    assert run(["a", "attach"]) == 0

    config = collaborators["load_config"].return_value
    batches.assert_called_once_with(config, "a", {"command": "batches"})
    drivers["run_tui"].assert_called_once_with(None, "a", config, attach=True)


def test_attach_from_a_built_argument_attaches_and_stops_nothing(
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    batches: mock.MagicMock,
) -> None:
    built = "".join(["att", "ach"])

    assert run(["a", built]) == 0

    config = collaborators["load_config"].return_value
    batches.assert_called_once_with(config, "a", {"command": "batches"})
    drivers["run_tui"].assert_called_once_with(None, "a", config, attach=True)


@pytest.mark.parametrize(
    "reply",
    [
        {"ok": True, "batches": []},
        {"ok": False, "error": "Unknown command batches"},
        ValueError("No daemon is running for a."),
    ],
)
def test_attach_with_nothing_running_says_so_and_opens_nothing(
    reply: object,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    batches: mock.MagicMock,
) -> None:
    if isinstance(reply, Exception):
        batches.side_effect = reply
    else:
        batches.return_value = reply
    drivers["sys"].stdout.isatty.return_value = False

    assert run(["a", "attach"]) == 0

    assert capsys.readouterr().out == "Nothing is running for a.\n"
    drivers["run_tui"].assert_not_called()


@pytest.mark.parametrize(("stdout", "stderr"), [(False, True), (True, False)])
def test_attach_without_a_terminal_is_a_usage_error(
    stdout: bool,
    stderr: bool,
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    batches: mock.MagicMock,
) -> None:
    drivers["sys"].stdout.isatty.return_value = stdout
    drivers["sys"].stderr.isatty.return_value = stderr

    assert run(["a", "attach"]) == 2

    assert "attach requires a terminal." in capsys.readouterr().err
    drivers["run_tui"].assert_not_called()


def test_attach_reports_a_tui_error(
    capsys: pytest.CaptureFixture[str],
    collaborators: dict[str, mock.MagicMock],
    drivers: dict[str, mock.MagicMock],
    batches: mock.MagicMock,
) -> None:
    drivers["run_tui"].side_effect = ValueError("No daemon is running for a.")

    assert run(["a", "attach"]) == 1

    assert "Error: No daemon is running for a." in capsys.readouterr().err
