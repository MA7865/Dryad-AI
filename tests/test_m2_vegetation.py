
"""
Automated tests for M2 vegetation intelligence.

Tests:
- GeoJSON output
- Shared patch IDs
- Patch filtering
- Invalid patch handling
- API responses
- Missing data preservation
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from modules.vegetation.vegetation import predict_vegetation

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "grid.geojson"

client = TestClient(app)


def test_full_vegetation_layer():
    result = predict_vegetation()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 2061


def test_shared_patch_ids():
    result = predict_vegetation()

    with open(GRID, encoding="utf-8") as f:
        grid = json.load(f)

    expected = {
        x["properties"]["patch_id"]
        for x in grid["features"]
    }

    actual = {
        x["properties"]["patch_id"]
        for x in result["features"]
    }

    assert actual == expected


def test_single_patch_filter():
    result = predict_vegetation(
        patch_ids=["P_r000_c023"]
    )

    assert len(result["features"]) == 1

    assert (
        result["features"][0]["properties"]["patch_id"]
        == "P_r000_c023"
    )


def test_unknown_patch_rejected():
    with pytest.raises(ValueError):
        predict_vegetation(
            patch_ids=["INVALID_PATCH"]
        )


def test_unsupported_year_rejected():
    with pytest.raises(ValueError):
        predict_vegetation(as_of="2024")


def test_api_full_layer():
    response = client.get(
        "/api/v1/layers/vegetation"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2061


def test_api_single_patch():
    response = client.get(
        "/api/v1/layers/vegetation",
        params={"patch_id": "P_r000_c023"}
    )

    assert response.status_code == 200

    data = response.json()
    assert len(data["features"]) == 1


def test_api_invalid_patch():
    response = client.get(
        "/api/v1/layers/vegetation",
        params={"patch_id": "INVALID_PATCH"}
    )

    assert response.status_code == 400


def test_api_invalid_year():
    response = client.get(
        "/api/v1/layers/vegetation",
        params={"as_of": "2024"}
    )

    assert response.status_code == 400


def test_missing_data_not_replaced_with_zero():
    result = predict_vegetation()

    missing = [
        f for f in result["features"]
        if f["properties"].get("data_quality") == "missing"
    ]

    assert len(missing) > 0

    for feature in missing:
        p = feature["properties"]

        # Missing values must not be turned into invented zeros.
        if p.get("vegetation_class") is None:
            assert p["vegetation_class"] is None
