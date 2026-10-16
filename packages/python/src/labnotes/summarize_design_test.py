from labnotes.summarize_design import summarize_design


def test_summarizes_the_grid_and_target() -> None:
    summary = summarize_design(
        {
            "study": "s",
            "script": "run.py",
            "runs_per_cell": 12,
            "completed_run": "exit_code = 0",
            "fixed": {"model": "opus"},
            "varies": {"lang": ["py", "js"], "effort": ["low", "medium", "high"]},
        }
    )

    assert summary["cell_count"] == 6
    assert summary["target"] == 72
    assert summary["completed_run"] == "exit_code = 0"
    assert summary["fixed"] == {"model": "opus"}
    assert summary["other"] == {"script": "run.py"}


def test_tolerates_a_bare_design() -> None:
    summary = summarize_design({})

    assert summary["cell_count"] == 1
    assert summary["target"] is None
    assert summary["completed_run"] == "1"
    assert summary["varies"] == {}


def test_wraps_a_scalar_varies_value() -> None:
    assert summarize_design({"varies": {"seed": 1}})["varies"] == {"seed": [1]}
