from labnotes.memory_interval import DEFAULT_MEMORY_INTERVAL


def test_samples_memory_every_5_seconds() -> None:
    assert DEFAULT_MEMORY_INTERVAL == 5.0
