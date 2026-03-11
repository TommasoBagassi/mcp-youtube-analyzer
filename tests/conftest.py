# tests/conftest.py
"""Pytest configuration and shared fixtures."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration", action="store_true", default=False,
        help="Run integration tests (requires network access)"
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip = pytest.mark.skip(reason="Need --integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(autouse=True)
def clear_transcript_cache():
    """Clear the transcript cache before each test to prevent cross-test pollution."""
    import youtube_analyzer.transcript as transcript_module
    transcript_module._transcript_cache.clear()
    yield
    transcript_module._transcript_cache.clear()
