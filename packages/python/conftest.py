import pytest


@pytest.fixture(autouse=True)
def state_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Run journals live under XDG_STATE_HOME; keep tests out of the real one.
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state")))
