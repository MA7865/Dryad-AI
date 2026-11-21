"""Test setup: make the repo importable and keep tests from calling Earth Engine."""
import os

os.environ.setdefault("M1_LIVE", "off")
