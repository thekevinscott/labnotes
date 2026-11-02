from labnotes.config_migration import MIGRATION, MISSING_CONTINUES, REMOVED_MODE


def test_points_both_errors_at_the_migration() -> None:
    assert MIGRATION.endswith("docs/migrations.d/2026-11-02-python-remove-modes.md")
    assert REMOVED_MODE.startswith("mode was removed")
    assert MISSING_CONTINUES.startswith(
        "continues is required: set continues = true or continues = false"
    )
    assert REMOVED_MODE.endswith(MIGRATION)
    assert MISSING_CONTINUES.endswith(MIGRATION)
