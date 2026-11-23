import os

os.environ.setdefault("M1_LIVE", "off")      # must be set before the app is imported

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from modules.forest_health.paths import LATEST

client = TestClient(app)
needs_summer = pytest.mark.skipif(
    not LATEST.exists(),
    reason="summer layer not built: python -m modules.forest_health.build_outputs")


@needs_summer
def test_summer_layer_has_all_patches():
    r = client.get("/api/v1/layers/forest-health")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2061
    props = body["features"][0]["properties"]
    for key in ("patch_id", "health_index", "health_band", "ndvi", "ndmi", "trend_label"):
        assert key in props


@needs_summer
def test_patch_panel():
    r = client.get("/api/v1/patches/P_r000_c024/forest-health")
    assert r.status_code == 200
    body = r.json()
    assert body["patch_id"] == "P_r000_c024"
    assert len(body["history"]) == 5


@needs_summer
def test_unknown_patch_is_404():
    assert client.get("/api/v1/patches/NOPE/forest-health").status_code == 404


def test_status_endpoint():
    r = client.get("/api/v1/layers/forest-health/status")
    assert r.status_code == 200
    assert "live_status" in r.json()


def test_live_layer_is_ready_or_not_yet():
    assert client.get("/api/v1/layers/forest-health?period=live").status_code in (200, 503)

def test_model_card_endpoint():
    r = client.get("/api/v1/layers/forest-health/model-card")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "evaluation" in r.json()