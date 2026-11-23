import pytest
from fastapi.testclient import TestClient

from backend.app.api import fires
from backend.app.main import app
from modules.fire_monitoring import FirmsError

client = TestClient(app)
EMPTY = {"type": "FeatureCollection", "features": []}
BODY = {"ignition_lon": -119.4987, "ignition_lat": 37.0140, "target_area_km2": 3.0,
        "wind_dir_deg": 272, "wind_k": 2.0, "seed": 0}


def test_active_fires_passes_params_and_returns_collection(monkeypatch):
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return EMPTY
    monkeypatch.setattr(fires, "get_active_fires", fake)
    r = client.get("/api/v1/fires/active",
                   params={"start": "2016-07-29", "end": "2016-08-02", "source": "VIIRS_SNPP_SP"})
    assert r.status_code == 200 and r.json() == EMPTY
    assert seen == {"start": "2016-07-29", "end": "2016-08-02", "source": "VIIRS_SNPP_SP"}


def test_active_fires_defaults(monkeypatch):
    monkeypatch.setattr(fires, "get_active_fires", lambda **kw: EMPTY)
    assert client.get("/api/v1/fires/active").status_code == 200


def test_firms_failure_is_502_not_empty(monkeypatch):
    def boom(**kw):
        raise FirmsError("down")
    monkeypatch.setattr(fires, "get_active_fires", boom)
    r = client.get("/api/v1/fires/active")
    assert r.status_code == 502
    assert "FIRMS" in r.json()["detail"]


def test_bad_dates_are_422(monkeypatch):
    def bad(**kw):
        raise ValueError("start must not be after end")
    monkeypatch.setattr(fires, "get_active_fires", bad)
    assert client.get("/api/v1/fires/active", params={"start": "2020-02-02", "end": "2020-01-01"}).status_code == 422


def test_unknown_source_is_422():
    assert client.get("/api/v1/fires/active", params={"source": "NOPE"}).status_code == 422


def test_fire_spread_returns_simulated_layer():
    r = client.post("/api/v1/simulations/fire-spread", json=BODY)
    assert r.status_code == 200
    feats = r.json()["features"]
    assert feats and all(f["properties"]["layer_type"] == "fire_spread" for f in feats)
    assert all(f["properties"]["data_kind"] == "simulated" for f in feats)


def test_fire_spread_same_seed_same_patches():
    a = client.post("/api/v1/simulations/fire-spread", json=BODY).json()["features"]
    b = client.post("/api/v1/simulations/fire-spread", json=BODY).json()["features"]
    assert [f["properties"]["patch_id"] for f in a] == [f["properties"]["patch_id"] for f in b]


@pytest.mark.parametrize("change", [
    {"ignition_lon": -120.0}, {"target_area_km2": 0}, {"target_area_km2": 500},
    {"wind_dir_deg": 400}, {"wind_k": 99}])
def test_fire_spread_bad_input_is_422(change):
    assert client.post("/api/v1/simulations/fire-spread", json={**BODY, **change}).status_code == 422
