"""Tests for M4's get_active_fires. They never call NASA: the network is replaced by fakes.

Run from the repo root:   python -m pytest tests/test_active_fire.py -v
"""
import re
from datetime import date

import pandas as pd
import pytest

from modules.fire_monitoring import FirmsError, get_active_fires
from modules.fire_monitoring import active_fire, firms_client

KEY = "ABCDEF0123456789ABCDEF0123456789"
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
COMMON = ["feature_id", "patch_id", "layer_type", "observed_at", "generated_at",
          "model_version", "source", "data_quality", "data_kind"]
M4_REQUIRED = ["detection_id", "confidence", "detection_time", "satellite_source"]
HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"
ROWS = [
    "37.10,-119.40,330.1,0.4,0.4,2016-08-01,912,N,VIIRS,n,1,290.0,9.61,N",
    "37.15,-119.30,340.0,0.4,0.4,2016-07-31,2105,N,VIIRS,h,1,295.0,20.5,D",
]


class FakeResponse:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status


@pytest.fixture(autouse=True)
def no_waiting_and_key(monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", KEY)
    monkeypatch.setattr(firms_client, "load_dotenv", lambda: None)
    monkeypatch.setattr(firms_client.time, "sleep", lambda s: None)


def fake_get(monkeypatch, text="", status=200):
    calls = []
    def _get(url, timeout=None):
        calls.append(url)
        return FakeResponse(text, status)
    monkeypatch.setattr(firms_client.requests, "get", _get)
    return calls


def test_date_chunks_split_into_five_day_requests():
    chunks = firms_client.date_chunks(date(2016, 7, 29), date(2016, 8, 10))
    assert chunks == [(date(2016, 7, 29), 5), (date(2016, 8, 3), 5), (date(2016, 8, 8), 3)]


def test_features_follow_the_contract(monkeypatch):
    fake_get(monkeypatch, "\n".join([HEADER] + ROWS))
    fc = get_active_fires(start="2016-07-31", end="2016-08-01", source="VIIRS_SNPP_SP")
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2
    for f in fc["features"]:
        p = f["properties"]
        for k in COMMON + M4_REQUIRED:
            assert k in p, k
        assert p["layer_type"] == "active_fire"
        assert p["patch_id"] and p["patch_id"].startswith("P_r")
        assert ISO_UTC.match(p["observed_at"]) and ISO_UTC.match(p["generated_at"])
        lon, lat = f["geometry"]["coordinates"]
        assert -119.50 <= lon <= -119.25 and 37.00 <= lat <= 37.20
    times = {f["properties"]["observed_at"] for f in fc["features"]}
    assert times == {"2016-08-01T09:12:00Z", "2016-07-31T21:05:00Z"}


def test_same_request_gives_same_ids(monkeypatch):
    fake_get(monkeypatch, "\n".join([HEADER] + ROWS))
    a = get_active_fires(start="2016-07-31", end="2016-08-01", source="VIIRS_SNPP_SP")
    b = get_active_fires(start="2016-07-31", end="2016-08-01", source="VIIRS_SNPP_SP")
    ids = lambda fc: [f["properties"]["feature_id"] for f in fc["features"]]
    assert ids(a) == ids(b)


def test_no_detections_is_an_empty_collection_not_an_error(monkeypatch):
    fake_get(monkeypatch, HEADER)                 # header only
    fc = get_active_fires(start="2026-11-09", end="2026-11-10")
    assert fc == {"type": "FeatureCollection", "features": []}


def test_long_range_makes_several_requests(monkeypatch):
    calls = fake_get(monkeypatch, HEADER)
    get_active_fires(start="2016-07-29", end="2016-08-10", source="VIIRS_SNPP_SP")
    assert len(calls) == 3


def test_bad_key_error_does_not_leak_the_key(monkeypatch):
    fake_get(monkeypatch, f"Invalid MAP_KEY {KEY}", status=403)
    with pytest.raises(FirmsError) as err:
        get_active_fires(start="2026-11-09", end="2026-11-10")
    assert "403" in str(err.value) and KEY not in str(err.value)


def test_temporary_server_error_is_retried_then_reported(monkeypatch):
    calls = fake_get(monkeypatch, "", status=503)
    with pytest.raises(FirmsError, match="3 attempts"):
        get_active_fires(start="2026-11-10", end="2026-11-10")
    assert len(calls) == 3


def test_network_failure_is_reported_without_the_url(monkeypatch):
    def boom(url, timeout=None):
        raise firms_client.requests.ConnectionError(f"could not reach {url}")
    monkeypatch.setattr(firms_client.requests, "get", boom)
    with pytest.raises(FirmsError) as err:
        get_active_fires(start="2026-11-10", end="2026-11-10")
    assert KEY not in str(err.value)


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("FIRMS_MAP_KEY")
    with pytest.raises(FirmsError, match="FIRMS_MAP_KEY"):
        get_active_fires(start="2026-11-10", end="2026-11-10")


def test_unexpected_text_reply_is_an_error(monkeypatch):
    fake_get(monkeypatch, "Invalid API call")
    with pytest.raises(FirmsError, match="Unexpected reply"):
        get_active_fires(start="2026-11-10", end="2026-11-10")


@pytest.mark.parametrize("bbox", [(-120.0, 37.0, -119.25, 37.2), (-119.25, 37.0, -119.5, 37.2)])
def test_bbox_outside_study_area_or_reversed_is_rejected(bbox):
    with pytest.raises(ValueError):
        get_active_fires(bbox=bbox, start="2026-11-10", end="2026-11-10")


def test_start_after_end_is_rejected():
    with pytest.raises(ValueError):
        get_active_fires(start="2026-11-10", end="2026-11-01")


def test_point_on_cell_edge_still_gets_one_patch():
    grid = active_fire.load_grid()
    corner = grid.geometry.iloc[0].exterior.coords[0]          # a shared cell corner/edge point
    df = pd.read_csv(pd.io.common.StringIO("\n".join([HEADER, f"{corner[1]},{corner[0]},330,0.4,0.4,2016-08-01,912,N,VIIRS,n,1,290,5.0,N"])))
    feats = active_fire.detections_to_features(df, "VIIRS_SNPP_SP")
    assert len(feats) == 1 and feats[0]["properties"]["patch_id"]


def test_low_confidence_detections_are_dropped(monkeypatch):
    low = "37.12,-119.35,320.0,0.4,0.4,2016-08-01,1000,N,VIIRS,l,1,290.0,1.0,D"
    fake_get(monkeypatch, "\n".join([HEADER] + ROWS + [low]))
    fc = get_active_fires(start="2016-07-31", end="2016-08-01", source="VIIRS_SNPP_SP")
    assert sorted(f["properties"]["confidence"] for f in fc["features"]) == ["h", "n"]


def test_features_carry_data_kind_observed(monkeypatch):
    fake_get(monkeypatch, "\n".join([HEADER] + ROWS))
    fc = get_active_fires(start="2016-07-31", end="2016-08-01", source="VIIRS_SNPP_SP")
    assert {f["properties"]["data_kind"] for f in fc["features"]} == {"observed"}
