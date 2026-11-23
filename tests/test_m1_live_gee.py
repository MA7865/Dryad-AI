import os
from datetime import date, timedelta

import pytest

from modules.forest_health import live_gee


@pytest.mark.skipif(os.getenv("M1_LIVE_TEST") != "1",
                    reason="set M1_LIVE_TEST=1 to call Earth Engine")
def test_real_earth_engine_window():
    newest = live_gee.latest_scene_date()
    assert (date.today() - date.fromisoformat(newest)).days <= 14      # imagery is recent
    end = (date.fromisoformat(newest) + timedelta(days=1)).isoformat()
    start = (date.fromisoformat(newest) - timedelta(days=29)).isoformat()
    df = live_gee.fetch_window_features(start, end)
    assert len(df) == 2061
    assert df["NDVI"].notna().sum() > 1900