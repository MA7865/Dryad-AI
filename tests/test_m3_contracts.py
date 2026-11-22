import json
import math
from pathlib import Path

import geopandas as gpd
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from modules.fire_monitoring.active_fire import load_grid as m4_load_grid
from modules.shared import grid as shared_grid
from modules.shared import weather
from scripts.build_patch_static_features import build as build_static

client = TestClient(app)
FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_forecast.json"


def test_shared_load_grid_matches_m4():
    shared = shared_grid.load_grid()
    m4 = m4_load_grid()
    assert len(shared) == 2061
    assert shared[["patch_id", "geometry"]].set_index("patch_id").geometry.to_dict() == m4.set_index("patch_id").geometry.to_dict()


@pytest.mark.parametrize("index", [0, 100, 2060])
def test_edge_and_normal_points_match_m4(index):
    grid = shared_grid.load_grid()
    patch = grid.iloc[index]
    lon, lat = patch.geometry.representative_point().x, patch.geometry.representative_point().y
    shared_id = shared_grid.point_to_patch_id(lon, lat)
    assert shared_id == patch["patch_id"]


def test_wind_toward_helper():
    assert weather.wind_toward_deg(270) == 90
    assert weather.wind_toward_deg(350) == 170
    assert weather.wind_toward_deg(None) is None


def test_nearest_point_index():
    points = [(37.0, -119.5), (37.2, -119.25)]
    assert weather.nearest_point_index([(37.01, -119.49), (37.19, -119.26)], points) == [0, 1]


def test_weather_fixture_offline(monkeypatch):
    fixture = json.loads(FIXTURE.read_text())
    monkeypatch.setattr(weather, "_request", lambda *args, **kwargs: fixture)
    rows = weather.get_forecast([(37.08, -119.38)], 2)
    assert len(rows) == 2
    assert rows[0]["wind_dir_deg"] == 270
    assert rows[0]["wind_toward_deg"] == 90
    assert rows[0]["wind_speed_ms"] == 5
    assert rows[0]["time"].endswith("Z")
    assert rows[0]["vpd_kpa"] is not None


@pytest.mark.live
def test_live_weather_is_optional():
    rows = weather.get_forecast([(37.08, -119.38)], 1)
    assert rows


def test_risk_stub_contract():
    response = client.get("/api/v1/layers/ignition-risk")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2061

    grid_ids = set(gpd.read_file("data/grid.geojson")["patch_id"])
    for feature in body["features"]:
        props = feature["properties"]
        assert props["patch_id"] in grid_ids
        assert props["layer_type"] == "ignition_risk"
        assert props["data_kind"] == "predicted"
        assert props["risk_score"] is None
        assert props["risk_percentile"] is None
        assert props["risk_band"] == "not_scored"
        assert props["model_status"] == "not_trained"
        assert props["data_quality"] == "stub"
        assert props["observed_at"] is None
        assert math.isfinite(props["row"]) and math.isfinite(props["col"])


def test_unknown_patch_and_status():
    assert client.get("/api/v1/patches/NOPE/ignition-risk").status_code == 404
    status = client.get("/api/v1/layers/ignition-risk/status")
    assert status.status_code == 200
    assert status.json()["model_status"] == "not_trained"


@pytest.mark.parametrize(
    "body,detail",
    [
        ({ "delta_temp_c": 11, "delta_wind_pct": 0, "delta_precip_pct": 0 }, "delta_temp_c"),
        ({ "delta_temp_c": 0, "delta_wind_pct": -51, "delta_precip_pct": 0 }, "delta_wind_pct"),
        ({ "delta_temp_c": 0, "delta_wind_pct": 0, "delta_precip_pct": 101 }, "delta_precip_pct"),
    ],
)
def test_scenario_rejects_out_of_range(body, detail):
    response = client.post("/api/v1/simulations/weather", json=body)
    assert response.status_code == 422
    assert detail in str(response.json()["detail"])


def test_scenario_contract():
    known_patch = shared_grid.load_grid().sort_values("patch_id").iloc[0]["patch_id"]
    response = client.post("/api/v1/simulations/weather", json={
        "delta_temp_c": 3,
        "delta_wind_pct": 20,
        "delta_precip_pct": -40,
        "patch_ids": [known_patch],
    })
    assert response.status_code == 200
    feature = response.json()["features"][0]["properties"]
    assert feature["data_kind"] == "scenario"
    assert feature["risk_score"] is None
    assert feature["baseline_risk_score"] is None
    assert feature["risk_change"] is None
    assert feature["scenario"]["delta_temp_c"] == 3


def test_openapi_documents_m3_response_schemas():
    schema = app.openapi()
    assert "/api/v1/layers/ignition-risk" in schema["paths"]
    assert "/api/v1/layers/ignition-risk/status" in schema["paths"]
    assert "/api/v1/patches/{patch_id}/ignition-risk" in schema["paths"]
    assert "/api/v1/weather/forecast" in schema["paths"]
    assert "/api/v1/simulations/weather" in schema["paths"]

    forecast = schema["paths"]["/api/v1/weather/forecast"]["get"]
    scenario = schema["paths"]["/api/v1/simulations/weather"]["post"]
    assert "response" not in forecast["responses"]["200"] or forecast["responses"]["200"]["description"]
    assert scenario["responses"]["200"]["description"]


def test_static_script_fails_clearly_without_dem(tmp_path):
    with pytest.raises(FileNotFoundError, match="Elevation"):
        build_static(tmp_path / "missing.tif")


def test_patch_static_features_match_grid():
    table = pd.read_csv("data/processed/patch_static_features.csv")
    grid = gpd.read_file("data/grid.geojson")
    assert len(table) == 2061
    assert table["patch_id"].nunique() == 2061
    assert set(table["patch_id"]) == set(grid["patch_id"])
    assert table["slope_deg"].dropna().between(0, 90).all()
    assert table["aspect_deg"].dropna().between(0, 360).all()
    assert not table["elev_m"].isin([-9999, 32767]).any()
    assert not table["slope_deg"].isin([32767, 65535]).any()
    assert not table["aspect_deg"].isin([-1, -9999, 32767]).any()
    assert not table["fuel_model"].isin([-9999, 32767]).any()
