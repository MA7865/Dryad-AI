"""Test setup: make the repo importable and keep tests from calling Earth Engine."""
import os
import pytest

os.environ.setdefault("M1_LIVE", "off")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls the live external service")


def pytest_collection_modifyitems(config, items):
    if os.getenv("M3_LIVE_TEST") == "1":
        return
    skip_live = pytest.mark.skip(reason="set M3_LIVE_TEST=1 to call the live Open-Meteo API")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
