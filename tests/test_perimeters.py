import json

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backend.app.api import fires as fires_api
from backend.app.main import app
from modules.fire_monitoring import get_perimeters, perimeters
from build_perimeters import build, to_iso_utc

CAL_FIRE_LIKE = gpd.GeoDataFrame({
    "FIRE_NAME": ["GOOSE", "OLD ONE", None],
    "YEAR_": [2016, "1990", None],
    "ALARM_DATE": ["2016/07/30 00:00:00+00", None, "2005-06-01T00:00:00Z"],
    "CONT_DATE": ["2016-08-09", None, None],
    "GIS_ACRES": [2241.0, 100.0, None],
    "CAUSE": [14, None, None],
    "AGENCY": ["USF", None, "CCO"],
}, geometry=[box(-119.45, 37.05, -119.40, 37.10), box(-119.40, 37.10, -119.35, 37.15),
             box(-119.30, 37.15, -119.28, 37.17)], crs="EPSG:4326").to_crs("EPSG:3857")


@pytest.fixture
def perimeter_file(tmp_path):
    out = build(CAL_FIRE_LIKE)
    path = tmp_path / "p.geojson"
    out.to_file(path, driver="GeoJSON")
    perimeters.reload_data()
    return path


def test_build_converts_acres_dates_and_nulls():
    out = build(CAL_FIRE_LIKE)
    goose = out[out.fire_name == "GOOSE"].iloc[0]
    assert goose.year == 2016 and goose.alarm_date == "2016-07-30T00:00:00Z"
    assert goose.containment_date == "2016-08-09T00:00:00Z"
    assert goose.area_ha == pytest.approx(906.9, abs=0.1)          # 2241 acres
    old = out[out.fire_name == "OLD ONE"].iloc[0]
    assert pd.isna(old.alarm_date) and pd.isna(old.containment_date)
    unnamed = out[out.fire_name.isna()].iloc[0]
    assert unnamed.year == 2005                                     # year taken from the alarm date
    assert pd.isna(unnamed.area_ha)


def test_to_iso_utc_handles_junk():
    assert to_iso_utc(None) is None and to_iso_utc("not a date") is None and to_iso_utc(float("nan")) is None


def test_get_perimeters_contract(perimeter_file):
    fc = get_perimeters(path=perimeter_file, generated_at="2026-11-19T00:00:00Z")
    assert len(fc["features"]) == 3
    for f in fc["features"]:
        p = f["properties"]
        assert p["layer_type"] == "fire_perimeter" and p["data_kind"] == "observed"
        assert p["overlaps_study_area"] is True and p["generated_at"] == "2026-11-19T00:00:00Z"
    json.dumps(fc, allow_nan=False)                                  # no NaN anywhere: nulls only


def test_year_filter(perimeter_file):
    names = lambda fc: [f["properties"]["fire_name"] for f in fc["features"]]    # noqa: E731
    assert names(get_perimeters(2016, 2016, path=perimeter_file)) == ["GOOSE"]
    assert names(get_perimeters(year_to=1999, path=perimeter_file)) == ["OLD ONE"]
    assert get_perimeters(2030, 2031, path=perimeter_file)["features"] == []


def test_bad_year_order_raises(perimeter_file):
    with pytest.raises(ValueError):
        get_perimeters(2020, 2010, path=perimeter_file)


def test_missing_file_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_perimeters(path=tmp_path / "nope.geojson")


def test_endpoint_returns_perimeters_and_filters(perimeter_file, monkeypatch):
    monkeypatch.setattr(fires_api, "get_perimeters",
                        lambda **kw: get_perimeters(path=perimeter_file, **kw))
    client = TestClient(app)
    r = client.get("/api/v1/fires/perimeters", params={"year_from": 2016, "year_to": 2016})
    assert r.status_code == 200 and len(r.json()["features"]) == 1
    assert client.get("/api/v1/fires/perimeters", params={"year_from": 2020, "year_to": 2010}).status_code == 422


def test_endpoint_503_when_file_not_built(monkeypatch):
    def nope(**kw):
        raise FileNotFoundError("x")
    monkeypatch.setattr(fires_api, "get_perimeters", nope)
    assert TestClient(app).get("/api/v1/fires/perimeters").status_code == 503
