from unittest import mock

from labnotes.runner.new_param_run_id import new_param_run_id

CHOICES: dict[str, list[object]] = {"m": ["a", "b"]}


def test_ends_the_param_name_with_a_random_hash() -> None:
    with mock.patch(
        "labnotes.runner.new_param_run_id.secrets.token_hex",
        side_effect=["beef", "cafe"],
    ) as token_hex:
        taken = mock.Mock(side_effect=[True, False])
        assert new_param_run_id({"m": "a"}, CHOICES, taken) == "a-cafe"
    token_hex.assert_called_with(2)
    assert [c.args[0] for c in taken.call_args_list] == ["a-beef", "a-cafe"]


def test_falls_back_to_a_haiku_when_nothing_varies() -> None:
    taken = mock.Mock(return_value=False)
    with mock.patch(
        "labnotes.runner.new_param_run_id.new_run_id", return_value="brave-fox"
    ) as new_run_id:
        assert new_param_run_id({"m": "a"}, {"m": ["a"]}, taken) == "brave-fox"
    new_run_id.assert_called_once_with(taken)
